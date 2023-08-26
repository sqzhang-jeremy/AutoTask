import os
import openai
from loguru import logger
import json
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")


class Suggest:
    def __init__(self, model) -> None:
        self.model = model
        self.modified_result = None
        self.insert_prompt = None

    def suggest(self):
        self.prompt_select = [
            {
                "role": "system",
                "content": """You are an AI assistant specialized in UI Automation. Based on user's intent and the current screen's components, your task is to analyze, understand the screen. SELECT the top five most possible components to the user's intent thinking step by step. Summarize your selections at the end of your response.
Think step by step, select the top five most possible components to the user's intent.
The components are organized as HTML format and after-click components are showed and warpped (if any) to support further reasoning.
Remember DO not select any components without id. Only select original components with id.
You can refer to some completed examples similar to user's intent. But don't follow the examples exactly, though; they serve only as hints.
Hint:
1, Some of the components may be warpped by its parent node (such as <div><node/></div>), thus it inherits attibutes from parent node. So when selecting candidates you should consider its relationship with its parent node's info.
Output only one JSON object structured like {"result":[]-the id of selected candidate,"reason":[]-reason for each candidate} at the end of your response. You must select five!
Sample output:{
    "result": [5,10,2,3,4],
    "reason":[
        "...",
        "...",
        "...",
        "...",
        "..."
    ]
}
                """
            },
            # {
            #     "role": "user",
            #     "content": """
            #         Intention:'send a message \"Hello\" to Bowen'
            #         Current path: -> Main interface of the WhatsApp application
            #         Components:
            #         '''HTML
            #         <p id=1 class='com.whatsapp:id/fab' description='New chat'></p>
            #         <button id=2 class='com.whatsapp:id/home_tab_layout' description='Calls'> Calls
            #             /* Below are predicted after-click components */
            #             <button description='Bowen'> </button>
            #         </button>
            #         <button id=3 class='com.whatsapp:id/home_tab_layout' description='Status'>Status
            #             /* Below are predicted after-click components */
            #             <p description='My Status'> </p>
            #             <button description='Add Status'> </button>
            #         </button>
            #         <button id=4 class='com.whatsapp:id/home_tab_layout' description='Community'>
            #             /* Below are predicted after-click components */
            #             <button description='Members'> </button>
            #             <button description='Add new Member'> </button>
            #             <p description='Connect'> </p>
            #         </button>
            #         <button id=5 class='com.whatsapp:id/menuitem_overflow' description='More options'>
            #             /* Below are predicted after-click components */
            #             <button description='Settings'> </button>
            #             <button description='WhatsApp Web'> </button>
            #         </button>
            #         <p id=6 class='com.whatsapp:id/menuitem_search' description='Search'></p>
            #         <p id=7 class='com.whatsapp:id/menuitem_camera' description='Camera'></p>
            #         <p id=8 class='' description='end-to-end encrypted'></p>
            #         <button id=9 class='com.whatsapp:id/contact_photo' description='Yellow'></button>
            #         <button id=10 class='com.whatsapp:id/contact_photo' description='Wang Bowen'></button>
            #         '''
            #     """
            # },
            # {
            #     "role": "assistant",
            #     "content": """
            #     <button id=5 class='com.whatsapp:id/menuitem_overflow' description='More options'>: This component represents the overflow menu, which often contains additional settings and options. It's a common place to find settings related to appearance and themes, including Dark mode.
            #     <button id=10 class='com.whatsapp:id/contact_photo' description='Wang Bowen'>: This component likely represents a contact or profile photo. Tapping on a contact or profile photo often reveals additional options and settings, which may include Dark mode or appearance-related settings.
            #     <button id=2 class='com.whatsapp:id/home_tab_layout' description='Calls'>: While this component represents the "Calls" tab, it is worth exploring as some apps provide accessibility options, including Dark mode, within the tab navigation.
            #     <button id=3 class='com.whatsapp:id/home_tab_layout' description='Status'>: Similar to the "Calls" tab, the "Status" tab might contain accessibility or appearance-related options, including Dark mode.
            #     <button id=4 class='com.whatsapp:id/home_tab_layout' description='Community'>: Although the description is empty for this component, it is worth exploring as it could potentially lead to settings related to appearance or themes, including Dark mode.
            #     So the top five most possible components to the user's intent are:
            #     {
            #         "result": [5,10,2,3,4],
            #         "reason":[
            #         "This component represents the overflow menu, which often contains additional settings and options. It's a common place to find settings related to appearance and themes, including Dark mode.",
            #         "This component likely represents a contact or profile photo. Tapping on a contact or profile photo often reveals additional options and settings, which may include Dark mode or appearance-related settings.",
            #         "While this component represents the 'Calls' tab, it is worth exploring as some apps provide accessibility options, including Dark mode, within the tab navigation.",
            #         "Similar to the 'Calls' tab, the 'Status' tab might contain accessibility or appearance-related options, including Dark mode.",
            #         "Although the description is empty for this component, it is worth exploring as it could potentially lead to settings related to appearance or themes, including Dark mode."
            #         ]
            #     }
            #     """
            # },
            {
                "role": "user",
                "content": """
                    Intention :'{}'.
                    Current path: {}
                    Components:
                    '''HTML
                    {}
                    '''
                    Examples from Library:
                    {}
                    You must select 5 components!
                """.format(self.model.task, self.model.current_path_str, self.model.extended_info,[j+":"+"=>".join(k) for j,k in zip(self.model.similar_tasks,self.model.similar_traces)])
            },
        ]

        if self.modified_result is not None:
            response_text = self.modified_result
        else:
            if self.insert_prompt:
                self.prompt_select.append(self.insert_prompt)
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=self.prompt_select,
                temperature=0,
            )
            response_text = response["choices"][0]["message"]["content"]
        print(response_text)
        self.resp = response_text
        candidate = json.loads(
            response_text[response_text.find("{"):response_text.find("}")+1])
        self.model.candidate = candidate["result"]
        self.model.candidate_reason = candidate["reason"]
        self.model.candidate_str = [
            self.model.screen.semantic_info_list[i-1] for i in self.model.candidate]
        print(self.model.candidate_str)
        result_json={}
        for i in range(len(self.model.candidate)):
            result_json[self.model.candidate_str[i]]=self.model.candidate_reason[i]
        log_info = {
            "Name":"Select",
            "Description":"This module is a selection model, selecting the 5 possible component without relativity ranking to be acted on catering to user's intent",
            "Note":"This individual module only select 5 highly related components,without ranking them,and without analyzing the correctness of the components aligning with user's content ",
            "Output": result_json,
        }
        self.model.log_json["@Module"].append(log_info)

    def update(self, advice: dict):
        self.update_prompt = [
            {
                "role": "system",
                "content": """
You are an intelligent [Select Module] updater. A [Select Module]'s task is to select the 5 possible component to be acted on current UI screen catering to user's intent.
Now, the [End Human User](represents ground-truth) has provided feedback (criticisms) regarding the selection result from this former LLM result.
You need to optimize the current [Select Module] based on this feedback and analyze how to utilize the feedback to this former LLM.
You are given the feedback from end-user and description of [Select Module], you have 2 strategies to update the [Select Module]:
1, [Insert]: Insert a slice prompt to the end of the original prompt of [Select Module]'s LLM based on the feedback, augmenting the decision process of it.
2, [Modify]: Step over the LLM decision process of [Select Module] and directly modify the original output result based on the feedback.
Think step-by-step about the process of updating the [Select Module] and output a json object structured like: {"strategy": Insert or Modify, "prompt": your inserted slice prompt, "output": your direct modified output based on the original output. Don't break the format}
"""
            }
        ]
        self.update_prompt.append({
            "role": "user",
            "content": """
                Feedback from end-user(ground-truth):{}
                """.format(advice)
        })
        self.update_prompt.append({
            "role": "user",
            "content": """
                Original Output of [Select Module]:{}
                """.format(self.resp)
        })
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=self.update_prompt,
            temperature=1,
        )
        response_text = response["choices"][0]["message"]["content"]
        print(response_text)
        resp = json.loads(
            response_text[response_text.find("{"):response_text.find("}")+1])
        
        strategy = resp["strategy"]
        prompt = resp["prompt"]
        output = resp["output"]
        if strategy == "Insert":
            self.insert_prompt = {
                "role": "user",
                "content": prompt,
            }
        else:
            self.modified_result = output


    def plan(self):
        """
        Plans the next step of the user's intent.
        """
        self.prompt_plan = [
            {
                "role": "system",
                "content":
                """You are an AI assistant specialized in UI Automation. Now you have successfully obtained the top five UI components that are most likely to align with the user's intent. Now, you need to determine the actions to be performed on each of these UI components. 
                There are two main types of actions: 
                    1,clicking on a component (no text parameter needed) 
                    2,editing a component (you should also determine the text parameter).
For each of the top five components, analyze the possible action to be taken and, if it involves an editing action, provide the corresponding text parameter as well. 
Reason step by step to provide the actions and text parameters for each component based on the user's intent and the context of the current screen.
Output a JSON object structured like 
{"candidate1":{"action": the action to be taken,either "click" or "edit", "text": the text parameter for the action if any (Optional),"reason": the reason},
"candidate2":same as above,
"candidate3":same as above,
"candidate4":same as above,
"candidate5":same as above,
} 
including each candidate although which may be irrelevant"""
            },
#             {
#                 "role": "user",
#                 "content": """
#                 Task: send a message "Hello" to Bowen
# Current Page : Whatsapp homepage:
# Candidates:
# ["<button id=8 class='com.whatsapp:id/contact_photo' description='Wang Bowen'> </button>", "<p id=5 class='com.whatsapp:id/menuitem_search' description='Search'> </p>", "<button id=1 class='com.whatsapp:id/home_tab_layout' description='Calls'> </button>", "<button id=2 class='com.whatsapp:id/home_tab_layout' description='Status'> </button>", "<button id=3 class='com.whatsapp:id/home_tab_layout' description='Community'> </button>"]"""
#             },
#             {
#                 "role": "assistant",
#                 "content": """{
#   "candidate1": {
#     "action": "click",
#     "text": null,
#     "reason": "To open Bowen's chat window to send a message."
#   },
#   "candidate2": {
#     "action": "edit",
#     "text": "Bowen",
#     "reason": "To filter contacts and find Bowen's chat to send a message."
#   },
#   "candidate3": {
#     "action": "click",
#     "text": null,
#     "reason": "Switching to the 'Calls' tab is not relevant to sending a message."
#   },
#   "candidate4": {
#     "action": "click",
#     "text": null,
#     "reason": "Switching to the 'Status' tab is not relevant to sending a message."
#   },
#   "candidate5": {
#     "action": "click",
#     "text": null,
#     "reason": "Switching to the 'Community' tab is not relevant to sending a message."
#   }
# }"""},
            {
                "role": "user",
                "content": """
                Task: {},
Current Page : {}:
Candidates:{}""".format(self.model.task, self.model.page_description, self.model.candidate_str)
            }
        ]
        # with open("logs/suggest_log{}.log".format(self.model.index), "a") as f:
        #     f.write("--------------------Plan--------------------\n")
        # log_file = logger.add(
        #     "logs/suggest_log{}.log".format(self.model.index), rotation="500 MB")
        # logger.debug("Plan for Model {}".format(self.model.index))
        # logger.info("Prompt: {}".format(json.dumps(self.prompt_plan[-1])))
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=self.prompt_plan,
            temperature=0,
        )
        response_text = response["choices"][0]["message"]["content"]
        response = json.loads(
            response_text)
        print(response)
        log_info = {
            "Name":"Plan",
            "Description":"This module is a plan module, planning the next action based on the selected components, whether click or edit",
            "Output": response
        }
        self.model.log_json["@Module"].append(log_info)
        self.model.candidate_action = [None]*5
        self.model.candidate_text = [None]*5
        # self.model.candidate_reason = [None]*5
        for i in range(1, 6):
            candidate = response.get("candidate{}".format(i))
            if candidate:
                self.model.candidate_action[i - 1] = candidate.get("action") if candidate.get(
                    "action") else ""
                self.model.candidate_text[i - 1] = candidate.get("text") if candidate.get(
                    "text") else ""
        
