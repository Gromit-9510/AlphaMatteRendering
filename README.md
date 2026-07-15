# Alpha Matte Renderer

A lightweight, powerful Blender 4.5+ addon designed to automate the rendering of isolated object alpha mattes using viewport rendering (OpenGL) and local view isolation.

This tool is designed for artists and developers who need to quickly output alpha-masked image sequences of specific objects without breaking their main scene layout, rendering setup, or active working state.

---

## 🚀 Key Features

* **Zero-Setup Isolation:** Instantly isolates selected objects in Local View and renders them against a transparent background.
* **Automatic State Restoration:** After rendering completes (or is cancelled), the addon automatically restores:
  * Original viewport overlays & gizmos visibility.
  * Film transparency settings.
  * Camera view states & object selections.
  * Original output filepaths and render formats.
* **Smart Folder Naming & Suffixes:** Organizes renders automatically in your `.blend` directory under `[BlendFile]/AlphaMatte/[Start]-[End][Suffix]/`.
* **Clipboard Parser:** Copied an existing render folder name (e.g., `0001-0250_test`)? Click **"Paste Folder Name"** to instantly restore that exact frame range and suffix in the UI.
* **Asynchronous Status Polling:** Uses background timers to clean up and restore Blender's state dynamically once the viewport render job finishes.

---

## 🛠️ Installation

1. Download the python script (e.g., `alpha_matte_renderer.py`).
2. Open Blender (version 4.5 or newer).
3. Go to **Edit > Preferences > Add-ons**.
4. Click **Install...** at the top right and select the downloaded `.py` file.
5. Enable the **Render: Alpha Matte Renderer** addon by checking its checkbox.

---

## 📖 How to Use

### Basic Workflow
1. **Select** the objects you want to render in the 3D Viewport.
2. Open the **Alpha Matte** tab in the Sidebar (**N-panel** on the right side of the 3D viewport).
3. Set your desired **Frame Range** (Start/End).
4. *(Optional)* Enter a **Folder Suffix** (e.g., `_v1`, `_highres`) to keep your output organized.
5. Click **Make Alpha Matte**.
6. The addon will isolate your selection, shift to camera view, hide viewport overlays, and trigger a fast OpenGL animation render. Once finished, your scene settings will revert to normal automatically!

> ⚠️ **Important:** You must save your `.blend` file before rendering, as the addon uses relative paths to save the outputs inside your project folder.

### 📋 The "Paste Folder Name" Feature
If you are iterating on a specific sequence, you can copy the output folder name from your OS file explorer (e.g., `0012-0080_wheels_v2`) to your clipboard, then click **Paste Folder Name** in the panel. The addon will automatically extract and apply:
* Start Frame: `12`
* End Frame: `80`
* Suffix: `_wheels_v2`

---

## 📂 Directory Structure

Renders are cleanly structured next to your `.blend` file:

```text
Your_Project_Directory/
├── your_scene.blend
└── AlphaMatte/
    └── 0001-0250_car_body/
        ├── 0001.png
        ├── 0002.png
        └── ...
