# ok-nte-enh

<div align="center">
  <p><strong>Automation tool for <em>Neverness To Everness</em> · Enhanced auto-combat edition</strong></p>
  <p>Image-recognition and audio-driven automation with support for background operation, auto combat, and dual-team Abyss.</p>
</div>

## About

> [!IMPORTANT]
> **This project is fully developed on top of [ok-nte](https://github.com/BnanZ0/ok-nte) and is an extension of ok-nte's auto-combat logic.**

This project is a fork of [ok-nte](https://github.com/BnanZ0/ok-nte). All core combat logic - character battles, auto-dodge, and dual-team Abyss - is inherited from ok-nte's combat system. This repository does not reinvent the wheel; it only adds characters and strategies and improves combat transitions on top of ok-nte, without changing its original design, and continuously syncs upstream changes to stay aligned with the ok-nte mainline.

In short: **ok-nte is the foundation, ok-nte-enh is an incremental combat extension for solo-farming the Abyss and AFK EXP.**

## ✨ Highlights

### Enhanced Auto Combat
- **New Character Iloy**: Added to dual-team Abyss recognition and auto-combat, supporting gather, heal, and dream-state burst linkage.
- **Multi-character Combo Optimization**: Optimized combos and collaboration for Baicang, Mint, Shinku, Zero, Chiz, and more.
- **Dual-team Auto Detection**: Improved team detection, combat session preservation, and strategy continuity when targets briefly drop.

### Convenient AFK Features
- **Button Farm Spot (dodge-only AFK)**: A new AFK spot in the 999 Nights task that only auto-dodges and never attacks, ideal for AFK EXP farming.
- **Background Operation**: Automate game actions while the game runs in the background.

### Dailies & Lifestyle
- **One-click Dailies**: Automatically complete daily routines, including EXP & Beetle Coins, Ability Upgrade materials, Arc Ascension materials, Console, Cafe Tasks, Cinema Date, and Bond Gifts.
- **Bond Gifts**: Automatically send gifts to characters.
- **Auto Fishing**: Fully automated fishing.
- **Auto Drum Rhythm Game**: Automatically complete drum rhythm games.
- **Owner's Selection**: Automatically loop entering and exiting stages (requires an in-game AFK build).
- **Auto Pink Paws Heist**: Automatically complete the Pink Paws Heist.

### Combat Assist
- **Character Center**: Custom combo lists and feature management, adapting to different character skins.
- **Audio Driven**: Auto dodge and counter based on audio feedback.
- **Skip Dialog**: Rapidly skip through story dialogs.
- **Fast Travel**: Automatic map teleportation.

### Entertainment
- **Auto Piano**: Automatically analyze MIDI tracks and play the piano.

## ⚠️ Disclaimer

> [!CAUTION]
> **This software is an open-source, free external tool intended for learning and exchange purposes only. It automates the gameplay of *Neverness To Everness* by interacting with the game solely through the existing UI.**
>
> - **Mechanism**: The program interacts with the game only by recognizing the existing UI; it does not modify any game files or code.
> - **Purpose**: It is intended to provide convenience and is not meant to disrupt game balance or provide unfair advantages.
> - **Account Risk**: Using automation tools may result in account penalties. Please fully understand the associated risks before use.
> - **Liability**: All issues and consequences arising from the use of this software are not related to this project or its developers.

> [!WARNING]
> **Per the *Neverness To Everness* Fair Play Declaration, the official policy strictly prohibits any third-party tools that undermine fair gameplay, including but not limited to auto-farming and skill acceleration. Verified violations may result in penalty deductions, account freezes, or permanent bans.**
>
> **You should fully understand and voluntarily assume all potential risks associated with using this tool.**

## 🖥️ System Requirements & Compatibility

*   **Operating System**: Windows
*   **Game Resolution**: 1920×1080 or higher (**16:9 aspect ratio only**)
*   **Game Language**: Simplified Chinese / English

## 🚀 Installation Guide

### Method 1: Using the Installer (Recommended)

This method is suitable for most users. It is simple, fast, and supports automatic updates. Download the latest installer from the **Releases** page of this repository.

### Method 2: Running from Source (For Developers)

This method requires a Python environment and is suitable for users who want to contribute, modify, or debug the code.

1.  **Prerequisites**: Ensure you have **Python 3.12** or a newer version installed.
2.  **Clone the repository**:
    ```bash
    git clone https://github.com/Guilliman-XIII/ok-nte-enh.git
    cd ok-nte-enh
    ```
3.  **Install dependencies**:
    ```bash
    uv sync
    # or
    pip install -r requirements.txt
    ```
4.  **Run the application**:
    ```bash
    # Run the standard version
    python main.py

    # Run the debug version (outputs more detailed logs)
    python main_debug.py
    ```

## 📖 Usage Guide

To ensure the program runs stably, please confirm the following configuration before use.

### 1. Pre-use Configuration (Required)

> [!IMPORTANT]
> Before starting the automation, please check and confirm the following settings:
>
> *   **Graphics Settings**
>     *   **Game Brightness**: Use the **default** in-game brightness.
>     *   **UI Settings**: **Disable** all settings that cause the UI to differ from the default; **UI Opacity** must be **1.0**.
>     *   **Graphics Filters**: **Disable** all graphics card filters and sharpening effects (e.g., NVIDIA Freestyle, AMD FidelityFX).
> *   **Resolution**: Recommended to use **1920×1080** or higher **16:9** resolutions.
> *   **Keybindings**: Please use the game's **default** keybindings.
> *   **Third-party Software**: Disable any overlays that display information on the game screen (e.g., MSI Afterburner's framerate counter).

> [!WARNING]
> **Window and System State Precautions**
> *   **Mouse Interference**: When the game window is in the **foreground**, do not move your mouse, as it will interfere with the program's simulated inputs.
> *   **Window State**: The game window can be in the background but **must not be minimized**.
> *   **System State**: Do not let your computer **turn off the display** or **lock the screen**, as this will interrupt the program.

### 2. Quick Start

1.  Navigate to the level or scene you want to automate.
2.  Click the **"Start"** button in the program's interface.

## 💬 Bug Reports & Feedback

If you encounter issues, feel free to report them via the [**Issues**](https://github.com/Guilliman-XIII/ok-nte-enh/issues) page of this repository. To help us quickly identify the problem, please provide:

*   **Screenshot**: A clear image of the error or unusual behavior.
*   **Log File**: Attach the `.log` file from the program's directory.
*   **Detailed Description**: What were you doing? What exactly happened? Can you reproduce the issue consistently, or does it happen randomly?

## 🔗 Acknowledgments

This project is **fully developed on top of [ok-nte](https://github.com/BnanZ0/ok-nte)**, extending its auto-combat logic, and all core combat logic is inherited from ok-nte. It also builds on the [ok-script](https://github.com/ok-oldking/ok-script) framework. Thanks to the ok-nte and ok-script developers and the open-source community.

## 📄 License

This project is open-sourced under the GPL-3.0 license. See [LICENSE](LICENSE) for details.