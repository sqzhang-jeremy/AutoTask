
from Graph import Edge
from Modules.utility import simplify_ui_element_id, sort_by_similarity
from Modules.utility import GPT, Task_UI_grounding_prompt, coverage, plan_prompt, process_action_info, simplify_ui_element
import json
import os
import numpy as np
import openai
import sys
sys.path.append('..')



class Evaluate():
    """
    Class for Evaluation Module in AutoTask.

    Attributes:
        model (AutoTaskModel): The model instance associated with the evaluation.
        score (list): A list of scores for each UI element.
        reason (list): A list of reasons for each score.
        weights (list): A list of weights for adjusting scores.
    """

    def __init__(self, model):
        self.model = model
        self.score = []
        self.reason = []
        self.weights = []

    @staticmethod
    def log_decorator(func):
        """
        Decorator for logging the evaluation process.

        Args:
            func (function): The function to be decorated.

        Returns:
            function: The wrapped function with logging capability.
        """

        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            # Log the current state and module information
            self.model.log_json["@History_operation"] = self.model.current_path_str
            self.model.log_json["@Current_Action"] = self.model.current_action if self.model.current_action else ""
            self.model.log_json["@Module"].append({
                "Name": "Evaluate",
                "Description": "This module is an evaluation module, evaluating the selected components of their contribution to fulfilling the user's intent",
                "Score": {key: item for key, item in zip(self.model.screen.semantic_info_no_warp_with_id, self.score)},
                "Punishment coefficient": self.weights,
                "GPT answer": self.resp
            })
            # Save the log to a file
            with open("logs/log{}.json".format(self.model.index+1), "w", encoding="utf-8") as f:
                json.dump(self.model.log_json, f, indent=4)
            return result
        return wrapper

    @log_decorator
    def evaluate(self, ACTION_TRACE):
        """
        Evaluate the current action trace and update the model's state.

        Args:
            action_trace (dict): The current action trace.

        Returns:
            str or list: 'wrong' if evaluation fails, or a list of scores.
        """
        if self.score_comp(ACTION_TRACE) == "wrong":
            self.model.current_action = "Back due to overall low scoring"
            return "wrong"
        self.select_top_one()
        return self.score

    def handle_cycle(self, curpage, ACTION_TRACE):
        """
        Handle cycles in the action trace to prevent infinite loops.

        Args:
            current_page (str): The current page in the GUI.
            action_trace (dict): The current action trace.
        """
        if ACTION_TRACE["ACTION_DESC"] and len(ACTION_TRACE["ACTION_DESC"]) > 0 and ACTION_TRACE["ACTION_DESC"][-1] == "BACK":
            return
        for page in ACTION_TRACE["PAGES"][:-1]:
            if coverage(page, curpage) >= 0.95:
                index = ACTION_TRACE["PAGES"].index(page)
                index_now = len(ACTION_TRACE["PAGES"])-1
                step = index_now-index
                temp = self.model
                for i in range(step):
                    temp = temp.prev_model if temp.prev_model else temp
                if temp:
                    node = temp.node_selected_id
                    node = self.model.screen.semantic_info_no_warp_with_id[node-1]
                    self.prompt.append({"role": "user", "content": """NOTE: Current UI was once visited in the history operation sequence, and at that time it chose to operate on {}. To avoid infinite cycling operation, give punishment to this element when you score it in this step""".format(node)})

    def score_comp(self, ACTION_TRACE):
        """
        Compute scores for each component based on the current action trace.

        Args:
            action_trace (dict): The current action trace.

        Returns:
            str: 'wrong' if the overall scoring is low, else None.
        """
        self.prompt = Task_UI_grounding_prompt(self.model.task, [ACTION_TRACE[key]
                                                                 for key in ACTION_TRACE.keys() if "Action" in key], self.model.screen.semantic_info_all_warp, self.model.predict_module.comp_json_simplified, self.model.evaluation_knowledge, self.model.long_term_UI_knowledge, hint=None)
        self.handle_cycle(curpage=self.model.screen.page_root.generate_all_text().split(
            "-"), ACTION_TRACE=ACTION_TRACE)
        similarity = sort_by_similarity(
            """You are a mobile UI expert acting as a "Judger". Your specialized role focuses on guiding the user to complete the user task on specific UI screen.
Your job is to choose the next UI element to be operated considering the user task, the history operation sequence, and the current UI. You should rate the available UI elements on the current page.
Task: {}.
History operation sequence: {}.
Current UI:{}
Please output the next element to be operated.""".format(self.model.task, [ACTION_TRACE[key] for key in ACTION_TRACE.keys() if "Action" in key], self.model.screen.semantic_info_no_warp_with_id), self.model.screen.semantic_info_no_warp_with_id)
        similarity = np.array([x[1] for x in similarity])
        self.resp = GPT(self.prompt, tag="evaluate"+str(self.model.index+1))
        scores = [1.0]*len(self.model.screen.semantic_info_no_warp_with_id)
        for key, rating in self.resp.items():
            if key.startswith('id_'):
                try:
                    idx = int(key[len('id_'):]) - 1
                    if 0 <= idx < len(scores):
                        scores[idx] = rating
                    else:
                        print(f"Warning: Index {idx} out of range for scores list with length {len(scores)}")
                except ValueError:
                    print(f"Warning: Could not parse ID from key: {key}")
        self.score = np.array(scores)+similarity
        if self.weights == []:
            self.weights = [1.0] * len(self.score)
        if all(value < 2.0 for value in self.score) and self.model.prev_model:
            return "wrong"
        self.score = (self.score * np.array(self.weights)
                      ).tolist() if self.weights != [] else self.score

    def select_top_one(self):
        """
        Select the top scoring UI element and update the model's current action.
        """
        top_index = np.argmax(self.score)
        self.model.node_selected = self.model.screen.semantic_info_no_warp_with_id[top_index]
        self.model.node_selected_warp = list(filter(
            lambda x: "id="+str(top_index+1) in x, self.model.screen.semantic_info_half_warp))[0]  # 包围后的完整的node字符串描述
        if 'editable' in self.model.node_selected and 'ineditable' not in self.model.node_selected:
            response = GPT(plan_prompt(self.model.task,
                                       self.model.screen.semantic_info_all_warp, self.model.node_selected, self.resp), tag="plan"+str(self.model.index+1))
            self.model.node_selected_action, self.model.node_selected_text = response.get(
                "action"), response.get("text")
        elif 'scroll' in self.model.node_selected:
            self.model.node_selected_action, self.model.node_selected_text = (
                'scroll_forward', None)
        else:
            self.model.node_selected_action, self.model.node_selected_text = (
                'click', None)
        self.model.node_selected_id = top_index+1
        self.model.current_action = process_action_info(
            self.model.node_selected_action, self.model.node_selected_text, simplify_ui_element(self.model.node_selected_warp))
        self.model.current_path.append(self.model.current_action)
        self.model.final_node = self.model.screen.semantic_nodes["nodes"][self.model.screen.semantic_info_no_warp.index(
            self.model.node_selected)]
        self.model.edge_in_graph = Edge(
            self.model.node_selected_action, self.model.node_selected_text, simplify_ui_element_id(self.model.node_selected))

    def update_weights(self, weights):
        """
        Update the punishing weights for scoring components.

        Args:
            weights (dict): The punishment weights to be applied.
        """
        w = [0]*len(self.model.screen.semantic_info_no_warp_with_id)
        for key, item in weights.items():
            if key.startswith("id_"):
                index = int(key.split("_")[1]) - 1
                w[index] = int(item)
        self.weights = (np.array(self.weights) *
                        np.array([(10-i)/10 for i in w])).tolist()
