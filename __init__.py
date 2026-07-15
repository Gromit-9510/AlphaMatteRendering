# SPDX-License-Identifier: GPL-3.0-or-later
# Alpha Matte Renderer Addon for Blender 4.5+
# Automates alpha matte rendering with local view isolation

bl_info = {
    "name": "Alpha Matte Renderer",
    "author": "Claude",
    "version": (1, 2, 1),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Alpha Matte",
    "description": "Automate alpha matte rendering with local view isolation",
    "category": "Render",
}

import bpy
import os
from bpy.props import IntProperty, BoolProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup


class AlphaMatteState:
    """
    Singleton class to store the original state before rendering.
    This ensures we can restore everything after rendering completes.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.reset()
        return cls._instance
    
    def reset(self):
        """Reset all stored state values."""
        self.is_rendering = False
        self.render_started = False
        self.original_film_transparent = None
        self.original_overlay_show = None
        self.original_gizmo_show = None
        self.was_in_local_view = False
        self.was_in_camera_view = False
        self.selected_objects = []
        self.active_object = None
        self.output_path = ""
        self.space_data = None
        self.context_area = None
        self.original_filepath = None
        self.original_file_format = None
        self.original_color_mode = None
        self.original_frame_start = None
        self.original_frame_end = None
        self.target_frame_end = None
    
    def store_state(self, context):
        """Store current viewport and render state."""
        space = context.space_data
        scene = context.scene
        
        self.original_film_transparent = scene.render.film_transparent
        
        if space and space.type == 'VIEW_3D':
            self.original_overlay_show = space.overlay.show_overlays
            self.original_gizmo_show = space.show_gizmo
            self.was_in_local_view = space.local_view is not None
            self.was_in_camera_view = (space.region_3d.view_perspective == 'CAMERA')
            self.space_data = space
        
        self.selected_objects = list(context.selected_objects)
        self.active_object = context.active_object
        
        self.is_rendering = True
        self.render_started = True
    
    def restore_state(self, context):
        """Restore all settings to their original state."""
        if not self.is_rendering:
            return
        
        scene = context.scene
        
        if self.original_film_transparent is not None:
            scene.render.film_transparent = self.original_film_transparent
        
        space = self.space_data
        if space:
            if self.original_overlay_show is not None:
                space.overlay.show_overlays = self.original_overlay_show
            if self.original_gizmo_show is not None:
                space.show_gizmo = self.original_gizmo_show
        
        if space and not self.was_in_local_view and space.local_view is not None:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            with context.temp_override(area=area, region=region):
                                bpy.ops.view3d.localview()
                            break
                    break
        
        if space:
            if self.was_in_camera_view and space.region_3d.view_perspective != 'CAMERA':
                space.region_3d.view_perspective = 'CAMERA'
            elif not self.was_in_camera_view and space.region_3d.view_perspective == 'CAMERA':
                space.region_3d.view_perspective = 'PERSP'
        
        try:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in self.selected_objects:
                if obj and obj.name in bpy.data.objects:
                    obj.select_set(True)
            if self.active_object and self.active_object.name in bpy.data.objects:
                context.view_layer.objects.active = self.active_object
        except Exception as e:
            print(f"Alpha Matte: Could not restore selection: {e}")
        
        self.reset()


_state = AlphaMatteState()


def restore_render_settings(context):
    """Restore render settings after rendering completes."""
    scene = context.scene
    
    if _state.original_filepath is not None:
        scene.render.filepath = _state.original_filepath
    if _state.original_file_format is not None:
        scene.render.image_settings.file_format = _state.original_file_format
    if _state.original_color_mode is not None:
        scene.render.image_settings.color_mode = _state.original_color_mode
    if _state.original_frame_start is not None:
        scene.frame_start = _state.original_frame_start
    if _state.original_frame_end is not None:
        scene.frame_end = _state.original_frame_end
    
    _state.restore_state(context)


def check_render_complete():
    """Timer function to check if OpenGL render is complete."""
    if not _state.is_rendering:
        return None
    
    try:
        is_running = bpy.app.is_job_running("RENDER")
    except AttributeError:
        is_running = False
        if _state.target_frame_end is not None:
            output_dir = _state.output_path
            if output_dir:
                last_frame_file = os.path.join(output_dir, f"{_state.target_frame_end:04d}.png")
                is_running = not os.path.exists(last_frame_file)
    
    if not is_running and _state.render_started:
        output_path = _state.output_path
        
        context = bpy.context
        restore_render_settings(context)
        
        if hasattr(bpy.types.Scene, 'alphamatte_suffix'):
            try:
                bpy.context.scene.alphamatte_suffix = ""
            except:
                pass
        
        print(f"Alpha Matte: Rendering complete. Output saved to: {output_path}")
        print("Alpha Matte: Settings automatically restored.")
        
        for area in bpy.context.screen.areas:
            area.tag_redraw()
        
        return None
    
    return 0.5


class ALPHAMATTE_OT_render(Operator):
    """Render alpha matte animation for selected objects"""
    bl_idname = "alphamatte.render"
    bl_label = "Make Alpha Matte"
    bl_description = "Isolate selected objects and render alpha matte animation"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.selected_objects:
            return False
        if context.area.type != 'VIEW_3D':
            return False
        if _state.is_rendering:
            return False
        return True
    
    def execute(self, context):
        return bpy.ops.alphamatte.frame_range_dialog('INVOKE_DEFAULT')


class ALPHAMATTE_OT_frame_range_dialog(Operator):
    """Dialog to set frame range for alpha matte rendering"""
    bl_idname = "alphamatte.frame_range_dialog"
    bl_label = "Alpha Matte Frame Range"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    frame_start: IntProperty(
        name="Start Frame",
        description="Start frame of the animation",
        default=1,
        min=0,
        max=1048574,
    )
    
    frame_end: IntProperty(
        name="End Frame",
        description="End frame of the animation",
        default=250,
        min=0,
        max=1048574,
    )
    
    use_scene_range: BoolProperty(
        name="Use Scene Range",
        description="Use the scene's frame range",
        default=True,
    )
    
    def invoke(self, context, event):
        scene = context.scene
        self.frame_start = scene.frame_start
        self.frame_end = scene.frame_end
        self.use_scene_range = True
        return context.window_manager.invoke_props_dialog(self, width=300)
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        selected_count = len(context.selected_objects)
        layout.label(text=f"Selected Objects: {selected_count}", icon='OBJECT_DATA')
        layout.separator()
        
        layout.prop(self, "use_scene_range")
        
        col = layout.column(align=True)
        col.enabled = not self.use_scene_range
        col.prop(self, "frame_start")
        col.prop(self, "frame_end")
        
        layout.separator()
        layout.prop(scene, "alphamatte_suffix", text="Folder Suffix")
        
        layout.separator()
        blend_path = bpy.data.filepath
        if blend_path:
            base_dir = os.path.dirname(blend_path)
            if self.use_scene_range:
                start = context.scene.frame_start
                end = context.scene.frame_end
            else:
                start = self.frame_start
                end = self.frame_end
            
            folder_name = f"{start:04d}-{end:04d}"
            suffix = scene.alphamatte_suffix
            if suffix:
                folder_name = f"{folder_name}{suffix}"
            
            output_preview = os.path.join(base_dir, "AlphaMatte", folder_name)
            layout.label(text="Output:", icon='FILE_FOLDER')
            layout.label(text=output_preview)
        else:
            layout.label(text="Save .blend file first!", icon='ERROR')
    
    def execute(self, context):
        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({'ERROR'}, "Please save the .blend file first")
            return {'CANCELLED'}
        
        if self.use_scene_range:
            frame_start = context.scene.frame_start
            frame_end = context.scene.frame_end
        else:
            frame_start = self.frame_start
            frame_end = self.frame_end
        
        if frame_start > frame_end:
            self.report({'ERROR'}, "Start frame cannot be greater than end frame")
            return {'CANCELLED'}
        
        _state.store_state(context)
        _state.target_frame_end = frame_end
        
        scene = context.scene
        
        base_dir = os.path.dirname(blend_path)
        alpha_matte_dir = os.path.join(base_dir, "AlphaMatte")
        
        folder_name = f"{frame_start:04d}-{frame_end:04d}"
        suffix = scene.alphamatte_suffix
        if suffix:
            folder_name = f"{folder_name}{suffix}"
        
        output_dir = os.path.join(alpha_matte_dir, folder_name)
        
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            self.report({'ERROR'}, f"Cannot create output directory: {e}")
            _state.restore_state(context)
            return {'CANCELLED'}
        
        _state.output_path = output_dir
        
        space = context.space_data
        if space.local_view is None:
            bpy.ops.view3d.localview()
        
        if space.region_3d.view_perspective != 'CAMERA':
            if scene.camera is None:
                self.report({'ERROR'}, "No active camera in scene")
                _state.restore_state(context)
                return {'CANCELLED'}
            space.region_3d.view_perspective = 'CAMERA'
        
        space.overlay.show_overlays = False
        space.show_gizmo = False
        
        scene.render.film_transparent = True
        
        _state.original_filepath = scene.render.filepath
        _state.original_file_format = scene.render.image_settings.file_format
        _state.original_color_mode = scene.render.image_settings.color_mode
        _state.original_frame_start = scene.frame_start
        _state.original_frame_end = scene.frame_end
        
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.filepath = os.path.join(output_dir, "")
        
        scene.frame_start = frame_start
        scene.frame_end = frame_end
        
        if not bpy.app.timers.is_registered(check_render_complete):
            bpy.app.timers.register(check_render_complete, first_interval=1.0)
        
        bpy.ops.render.opengl('INVOKE_DEFAULT', animation=True)
        
        self.report({'INFO'}, f"Rendering alpha matte to: {output_dir}")
        return {'FINISHED'}


class ALPHAMATTE_OT_restore(Operator):
    """Manually restore viewport settings if something went wrong"""
    bl_idname = "alphamatte.restore"
    bl_label = "Restore Settings"
    bl_description = "Manually restore viewport and render settings"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        if _state.is_rendering:
            if bpy.app.timers.is_registered(check_render_complete):
                bpy.app.timers.unregister(check_render_complete)
            
            restore_render_settings(context)
            
            if hasattr(bpy.types.Scene, 'alphamatte_suffix'):
                context.scene.alphamatte_suffix = ""
            
            self.report({'INFO'}, "Settings restored")
        else:
            self.report({'WARNING'}, "No stored state to restore")
        return {'FINISHED'}


class ALPHAMATTE_OT_paste_folder_name(Operator):
    """Paste folder name from clipboard and extract frame range and suffix"""
    bl_idname = "alphamatte.paste_folder_name"
    bl_label = "Paste from Clipboard"
    bl_description = "Parse folder name from clipboard"
    
    def execute(self, context):
        import re
        
        clipboard_text = context.window_manager.clipboard.strip()
        
        if not clipboard_text:
            self.report({'WARNING'}, "Clipboard is empty")
            return {'CANCELLED'}
        
        folder_name = os.path.basename(clipboard_text)
        
        pattern = r'^(\d{4})-(\d{4})(.*)$'
        match = re.match(pattern, folder_name)
        
        if not match:
            self.report({'ERROR'}, f"Invalid folder name format: '{folder_name}'")
            return {'CANCELLED'}
        
        start_frame = int(match.group(1))
        end_frame = int(match.group(2))
        suffix = match.group(3)
        
        scene = context.scene
        scene.frame_start = start_frame
        scene.frame_end = end_frame
        scene.alphamatte_suffix = suffix
        
        if suffix:
            self.report({'INFO'}, f"Parsed: {start_frame}-{end_frame} with suffix '{suffix}'")
        else:
            self.report({'INFO'}, f"Parsed: {start_frame}-{end_frame} (no suffix)")
        
        return {'FINISHED'}


class ALPHAMATTE_OT_open_output(Operator):
    """Open the output folder in file browser"""
    bl_idname = "alphamatte.open_output"
    bl_label = "Open Output Folder"
    bl_description = "Open the AlphaMatte output folder"
    
    @classmethod
    def poll(cls, context):
        blend_path = bpy.data.filepath
        if not blend_path:
            return False
        base_dir = os.path.dirname(blend_path)
        alpha_dir = os.path.join(base_dir, "AlphaMatte")
        return os.path.exists(alpha_dir)
    
    def execute(self, context):
        blend_path = bpy.data.filepath
        base_dir = os.path.dirname(blend_path)
        alpha_dir = os.path.join(base_dir, "AlphaMatte")
        
        import subprocess
        import sys
        
        if sys.platform == 'win32':
            os.startfile(alpha_dir)
        elif sys.platform == 'darwin':
            subprocess.run(['open', alpha_dir])
        else:
            subprocess.run(['xdg-open', alpha_dir])
        
        return {'FINISHED'}


class ALPHAMATTE_PT_main_panel(Panel):
    """Main panel for Alpha Matte Renderer"""
    bl_label = "Alpha Matte"
    bl_idname = "ALPHAMATTE_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Alpha Matte"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        if _state.is_rendering:
            layout.label(text="Rendering in progress...", icon='RENDER_ANIMATION')
            layout.operator("alphamatte.restore", text="Cancel & Restore", icon='CANCEL')
            layout.separator()
            box = layout.box()
            box.label(text="Auto-restore on completion", icon='CHECKMARK')
            box.label(text="(Using timer polling)")
            return
        
        selected_count = len(context.selected_objects)
        if selected_count > 0:
            box = layout.box()
            box.label(text=f"Selected: {selected_count} object(s)", icon='OBJECT_DATA')
            
            for i, obj in enumerate(context.selected_objects[:3]):
                box.label(text=f"  • {obj.name}")
            if selected_count > 3:
                box.label(text=f"  ... and {selected_count - 3} more")
        else:
            layout.label(text="No objects selected", icon='ERROR')
        
        layout.separator()
        
        col = layout.column(align=True)
        col.label(text="Frame Range:", icon='RENDER_ANIMATION')
        row = col.row(align=True)
        row.prop(scene, "frame_start", text="Start")
        row.prop(scene, "frame_end", text="End")
        
        layout.separator()
        
        col = layout.column(align=True)
        col.prop(scene, "alphamatte_suffix", text="Folder Suffix")
        col.label(text="Tip: Use '_suffix' or ' suffix'", icon='INFO')
        
        layout.operator("alphamatte.paste_folder_name", text="Paste Folder Name", icon='PASTEDOWN')
        
        layout.separator()
        
        col = layout.column(align=True)
        col.scale_y = 1.5
        col.operator("alphamatte.render", icon='RENDER_ANIMATION')
        
        layout.separator()
        
        row = layout.row(align=True)
        row.operator("alphamatte.open_output", text="Open Output", icon='FILE_FOLDER')
        
        layout.separator()
        if bpy.data.filepath:
            base_dir = os.path.dirname(bpy.data.filepath)
            alpha_dir = os.path.join(base_dir, "AlphaMatte")
            if os.path.exists(alpha_dir):
                subfolders = [f for f in os.listdir(alpha_dir) if os.path.isdir(os.path.join(alpha_dir, f))]
                layout.label(text=f"Existing renders: {len(subfolders)}", icon='FILE_FOLDER')
        else:
            layout.label(text="Save file to enable rendering", icon='INFO')


class ALPHAMATTE_PT_help_panel(Panel):
    """Help panel for Alpha Matte Renderer"""
    bl_label = "How to Use"
    bl_idname = "ALPHAMATTE_PT_help_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Alpha Matte"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        
        col = layout.column(align=True)
        col.label(text="1. Select objects for matte")
        col.label(text="2. Set frame range")
        col.label(text="3. (Optional) Enter folder suffix")
        col.label(text="4. Click 'Make Alpha Matte'")
        col.label(text="5. Wait for render to complete")
        
        layout.separator()
        
        col = layout.column(align=True)
        col.label(text="Output Location:", icon='FILE_FOLDER')
        col.label(text="  [BlendFile]/AlphaMatte/")
        col.label(text="  [Start]-[End][Suffix]/")
        
        layout.separator()
        
        col = layout.column(align=True)
        col.label(text="Suffix Examples:", icon='INFO')
        col.label(text="  '_test' = 0001-0250_test")
        col.label(text="  ' test' = 0001-0250 test")
        col.label(text="  'test' = 0001-0250test")
        
        layout.separator()
        
        col = layout.column(align=True)
        col.label(text="Paste Folder Name:", icon='PASTEDOWN')
        col.label(text="  1. Copy folder name")
        col.label(text="  2. Click Paste button")
        col.label(text="  3. Auto-fills settings")
        
        layout.separator()
        
        col = layout.column(align=True)
        col.label(text="Notes:", icon='INFO')
        col.label(text="Uses viewport render")
        col.label(text="Output: PNG with alpha")
        col.label(text="Settings auto-restore")


classes = (
    ALPHAMATTE_OT_render,
    ALPHAMATTE_OT_frame_range_dialog,
    ALPHAMATTE_OT_restore,
    ALPHAMATTE_OT_paste_folder_name,
    ALPHAMATTE_OT_open_output,
    ALPHAMATTE_PT_main_panel,
    ALPHAMATTE_PT_help_panel,
)


def register():
    bpy.types.Scene.alphamatte_suffix = StringProperty(
        name="Suffix",
        description="Optional suffix to add to output folder name",
        default="",
        maxlen=64,
    )
    
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if bpy.app.timers.is_registered(check_render_complete):
        bpy.app.timers.unregister(check_render_complete)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    if hasattr(bpy.types.Scene, 'alphamatte_suffix'):
        del bpy.types.Scene.alphamatte_suffix


if __name__ == "__main__":
    register()