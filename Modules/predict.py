import json
import os
import openai

from Modules.utility import sort_by_similarity_score, sort_by_similarity_with_index



class Predict():
    """
    Predict class for predicting UI changes in AutoTask.

    Attributes:
        model (AutoTaskModel): The model instance associated with prediction.
    """

    def __init__(self, model):
        self.model = model

    def log_decorator(func):
        """
        Decorator for logging the prediction process.

        Args:
            func (function): The function to be decorated.

        Returns:
            function: The wrapped function with logging capability.
        """

        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            self.model.log_json["@Module"].append({
                "Name": "Predict",
                "Description": "This module is a prediction model, predicting what will appear after clicking each components on current screen",
                "One-step UI knowledge": self.comp_json_simplified,
                "Multi-step UI knowledge": self.model.long_term_UI_knowledge if self.model.load else ""
            })
            if not os.path.exists("logs"):
                os.mkdir("logs")
                with open("logs/log{}.json".format(self.model.index+1), "w", encoding="utf-8") as f:
                    json.dump(self.model.log_json, f, indent=4)
            return result
        return wrapper

    def one_step_UI_grounding(self):
        """
        Perform one-step UI grounding to predict the immediate UI changes in the UI graph
        """
        # Extract semantic information from the current UI
        SEMANTIC_INFO = list(
            filter(lambda x: "id=" in x, self.model.screen.semantic_info_no_warp))
        self.current_comp = SEMANTIC_INFO
        self.next_comp = ["Unknown"]*len(SEMANTIC_INFO)
        # Find next components based on the graph edges
        node = self.model.refer_node
        graph = node.graph
        edges = graph.find_neighbour_edges(node)
        edges_node = list(map(lambda x: str(x.node), edges))
        for i, e in enumerate(SEMANTIC_INFO):
            sims = sort_by_similarity_score(e, edges_node)
            if sims and max(sims) > 0.97:
                index = sims.index(max(sims))
                target_node = edges[index]._to
                self.next_comp[i] = target_node.elements
            else:
                continue
        # Filter out unknown components and sort by similarity
        self.next_comp = [(index, item) for index, item in enumerate(
            self.next_comp) if item != "Unknown"]
        sims = sort_by_similarity_with_index(
            self.model.task, ["--".join(x[1]) for x in self.next_comp], [x[0] for x in self.next_comp])
        sims = sorted(sims, key=lambda x: x[2], reverse=True)[:4]
        sims = sorted(sims, key=lambda x: x[0])
        # Simplify the component json
        self.comp_json_simplified = {
            "id="+str(index): item.split("--")
            for index, item, score in sims
            if item != "Unknown"
        }

    def multi_step_UI_grounding(self):
        """
        Perform multi-step UI grounding for long term predictions.
        """
        node = self.model.refer_node
        graph = node.graph
        target_UI, target_content = graph.find_target_UI(
            query="Which component may be relevant to this UI task? :"+self.model.task, refer_node=self.model.refer_node)
        if target_UI != [] and target_content != []:
            target_UI_path = []
            for target in target_UI:
                path = graph.find_shortest_road_to(node, target)
                if path is not None:
                    target_UI_path.append(path)
            self.model.long_term_UI_knowledge = dict(
                zip([" ".join(sublist) for sublist in target_content], target_UI_path))
        else:
            self.model.long_term_UI_knowledge = None

    def UI_grounding(self):
        """
        Ground the UI predictions for both one-step and multi-step scenarios.
        """
        self.one_step_UI_grounding()
        if self.model.load:
            self.multi_step_UI_grounding()

    @ log_decorator
    def predict(self, ACTION_TRACE=None):
        """
        Predict the UI changes based on the current action trace.

        Args:
            action_trace (dict): The current action trace, if any.
        """
        self.UI_grounding()
