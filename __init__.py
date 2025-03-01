import sys
import os
import bpy
import re

bl_info = {
    "name": "GPT-4 Blender Assistant",
    "blender": (2, 82, 0),
    "category": "Object",
    "author": "Aarya (@gd3kr)",
    "version": (1, 0, 0),
    "location": "3D View > UI > GPT-4 Blender Assistant",
    "description": "Generate Blender Python code using OpenAI's GPT-4 to perform various tasks.",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
}

system_prompt = """You are an assistant made for the purposes of helping the user with Blender, the 3D software. 
- Respond with your answers in markdown (```). 
- Preferably import entire modules instead of bits. 
- Do not perform destructive operations on the meshes. 
- Do not use cap_ends. Do not do more than what is asked (setting up render settings, adding cameras, etc)
- Do not respond with anything that is not Python code.

Example:

user: create 10 cubes in random locations from -10 to 10
assistant:
```
import bpy
from random import randint
bpy.ops.mesh.primitive_cube_add()

#how many cubes you want to add
count = 10

for c in range(0,count):
    x = randint(-10,10)
    y = randint(-10,10)
    z = randint(-10,10)
    bpy.ops.mesh.primitive_cube_add(location=(x,y,z))
```"""


# Add the 'libs' folder to the Python path
libs_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
if libs_path not in sys.path:
    sys.path.append(libs_path)



import openai

def get_api_key(context):
    preferences = context.preferences
    addon_prefs = preferences.addons[__name__].preferences
    return addon_prefs.api_key


def init_props():
    bpy.types.Scene.gpt4_natural_language_input = bpy.props.StringProperty(
        name="Command",
        description="Enter the natural language command",
        default="",
    )
    bpy.types.Scene.gpt4_button_pressed = bpy.props.BoolProperty(default=False)



def clear_props():
    del bpy.types.Scene.gpt4_natural_language_input
    del bpy.types.Scene.gpt4_button_pressed


def generate_blender_code(prompt):



    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{
                "role": "system",
                "content": system_prompt
            },
                {"role": "user", "content": "Can you please write Blender code for me that accomplishes the following task: " + prompt + "? \n. Do not respond with anything that is not Python code. Do not provide explanations"}
            ],
            stream=True,
            max_tokens=1500,
        )
    except Exception as e: # Use GPT-3.5 if GPT-4 is not available
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "system",
                "content": system_prompt
            },
                {"role": "user", "content": "Can you please write Blender code for me that accomplishes the following task: " + prompt + "?\nDo not respond with anything that is not Python code. Do not provide explanations"}
            ],
            stream=True,
            max_tokens=1500,
        )

    try:
        collected_events = []
        completion_text = ''
        # iterate through the stream of events
        for event in response:
            if 'role' in event['choices'][0]['delta']:
                # skip
                continue
            if len(event['choices'][0]['delta']) == 0:
                # skip
                continue
            collected_events.append(event)  # save the event response
            event_text = event['choices'][0]['delta']['content']
            completion_text += event_text  # append the text
            print(completion_text, flush=True, end='\r')
        completion_text = re.findall(r'```(.*?)```', completion_text, re.DOTALL)[0]
        # remove "python" if the first line has it
        completion_text = re.sub(r'^python', '', completion_text, flags=re.MULTILINE)
        
        return completion_text
    except IndexError:
        return None


class GPT4_PT_Panel(bpy.types.Panel):
    bl_label = "GPT-4 Blender Assistant"
    bl_idname = "GPT4_PT_Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GPT-4 Assistant'

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        column.label(text="Enter a natural language command:")

        # Add the input field for natural language commands
        column.prop(context.scene, "gpt4_natural_language_input", text="")

        # Execute the operator with the input from the user
        button_label = "Please wait...(this might take some time)" if context.scene.gpt4_button_pressed else "Execute"
        operator = column.operator("gpt4.execute", text=button_label)
        operator.natural_language_input = context.scene.gpt4_natural_language_input

        column.separator()


class GPT4_OT_Execute(bpy.types.Operator):
    bl_idname = "gpt4.execute"
    bl_label = "GPT-4 Execute"
    bl_options = {'REGISTER', 'UNDO'}

    natural_language_input: bpy.props.StringProperty(
        name="Command",
        description="Enter the natural language command",
        default="",
    )

    def execute(self, context):
        openai.api_key = get_api_key(context)

        if not openai.api_key:
            self.report({'ERROR'}, "No API key detected. Please set the API key in the addon preferences.")
            return {'CANCELLED'}

        context.scene.gpt4_button_pressed = True
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        
        blender_code = generate_blender_code(self.natural_language_input)

        if blender_code:
            # Add this line to print the generated code.
            print("Generated code:", blender_code)
            try:
                exec(blender_code)
            except Exception as e:
                self.report({'ERROR'}, f"Error executing generated code: {e}")
                context.scene.gpt4_button_pressed = False
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "Failed to generate Blender Python code")
            context.scene.gpt4_button_pressed = False
            return {'CANCELLED'}

        context.scene.gpt4_button_pressed = False
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(GPT4_OT_Execute.bl_idname)

class GPT4AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    api_key: bpy.props.StringProperty(
        name="API Key",
        description="Enter your OpenAI API Key",
        default="",
        subtype="PASSWORD",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_key")

def register():
    bpy.utils.register_class(GPT4AddonPreferences)
    bpy.utils.register_class(GPT4_OT_Execute)
    bpy.utils.register_class(GPT4_PT_Panel)
    bpy.types.VIEW3D_MT_mesh_add.append(menu_func)
    init_props()


def unregister():
    bpy.utils.unregister_class(GPT4AddonPreferences)
    bpy.utils.unregister_class(GPT4_OT_Execute)
    bpy.utils.unregister_class(GPT4_PT_Panel)
    bpy.types.VIEW3D_MT_mesh_add.remove(menu_func)
    clear_props()


if __name__ == "__main__":
    register()
