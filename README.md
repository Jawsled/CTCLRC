# CTCLRC

CTCLRC is a Windows & Linux desktop application that generates **LRC lyric timing files** from the following two inputs:

* An audio file
* A complete and accurate plain lyrics source

The application uses **CTC Forced Alignment**.

The lyrics text is treated as the ground truth, and the application estimates timestamps for each lyric line.

Android users should use [CTCLRC-droid](https://github.com/Kdroidwin/CTCLRCdroid).

---

## Usage

Use the packaged Windows application:

0. Build the executable.
1. Launch the application (a splash screen shows while it loads).
2. Set generation parameters (Language, by-line/charsync, embed)
3. Configure if the application should check LRClib for existing lyrics
4. Hit `generate`
5. Once generated, use the `Lyric Viewer / Editor` button to check if the timings are correct. If not, you can edit the timings: double-click cells to edit, `Tap-sync` to re-tap timings line by line while the song plays (`Space`/`T` per line), `Fix Timestamps` / `Shift Times` for batch corrections, and `Ctrl+Z` / `Ctrl+Y` to undo/redo.
6. Once done, you can save edited lyrics, and optionally, you can publish them on lrclib to help others.

- The generated `.lrc` file is saved in the same folder as the audio file.

---

## System Requirements

### Minimum Requirements

| Component | Minimum |
|----------|---------|
| OS | Windows 10 (64-bit) |
| CPU | Intel Core i5-8600 / AMD Ryzen 5 2600|
| Memory | 8 GB RAM |
| Storage | 2 GB available SSD space |
| GPU | Not required (CPU mode) |

### Recommended Requirements

| Component | Recommended |
|----------|-------------|
| OS | Windows 10/11 (64-bit) |
| CPU | Intel Core i5-12400 / AMD Ryzen 5 5600 or better |
| Memory | 16+ GB RAM |
| Storage | NVMe SSD / Is there such thing as too much storage? |
| GPU | Nvidia or AMD GPU with Torch / 6GB+ VRAM| 


### Notes

- CPU-only inference is fully supported, though slower than GPU inference.
- In GPU mode, the generation will be significantly faster. For GPU mode to work, you need to install appropriate Torch versions. (CUDA/ROCm)
- The first launch downloads the alignment model (approximately 1–2 GB depending on the model format) unless it is bundled with the application.
- Longer audio files require proportionally more processing time.
- More complex tracks (especially autotunes, vocal chops) may benefit from separation with somehting like [UVR](https://ultimatevocalremover.com/) then using vocal only for the processing.

---

## Building on Windows

### Install Dependencies

Run the following command from the project root directory:

```
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
#### For Nvidia GPU users + AMD GPU users on Linux
- Select appropriate options at [Pytorch Website](https://pytorch.org/get-started/locally/) to get correct installation commands.
- Install Pytorch in the venv (run `.venv\scripts\activate` to enter venv)

    Once installed and confirmed torch and CUDA device is visible, you can manually build your executable.

#### For AMD GPU users on Windows

- For AMD ROCm + Pytorch support, refer to official instructions from AMD, since Torch on ROCm is not officially distributed at Pytorch.org.
- Install ROCm + Pytorch in the venv (run `.venv\scripts\activate` to enter venv)

    [ROCm Docs - Install PyTorch for ROCm](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html)
    [ROCm Docs - PyTorch via PIP installation](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html?fam=radeon&os=windows&rocm-ver=10.0.0&pytorch-ver=2.12.0&i=pip&w=compute&gpu=amd-radeon-rx-9070-xt&gfx=gfx1201)

    Once installed and confirmed torch and CUDA device is visible, you can manually build your executable.
---

If you have a local copy of the `ctc-forced-aligner` ZIP package:

```
.\.venv\Scripts\python.exe -m pip install path\to\ctc-forced-aligner-main.zip
```

### Build

```
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm CTCLRC.spec
```
- It may take 15+ minutes if you include torch, just go make a coffee or tea or what have you.

Output:

```
dist\CTCLRC\CTCLRC.exe
```

## Important Distribution Notes

Builds use the **directory (One-Dir)** PyInstaller specification:

```
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm CTCLRC.spec
```

Output:

```
dist\CTCLRC\CTCLRC.exe
```

The output is a folder: `CTCLRC.exe` plus its support files. The directory
build starts much faster than a single-file build (no multi-GB unpack to a
temp dir on every launch) and is used together with the startup splash screen.

Move the whole `dist\CTCLRC` folder together and run `CTCLRC.exe` from inside it.

---

## Alignment Model

The application uses the following components:

* `ctc-forced-aligner`
* `MahmoudAshraf/mms-300m-1130-forced-aligner`

If the model is not bundled, the application automatically downloads it from Hugging Face during the first run and reuses the local cache afterward.

To create a fully offline executable, place the downloaded model in the following location before building:

```
models/mms-300m-1130-forced-aligner/
```

If the `models/` directory exists, `CTCLRC.spec` automatically bundles it into the application.

The application also checks for the following directory next to the executable at runtime:

```
models/mms-300m-1130-forced-aligner/
```

---

## Optional Offline Model Download

```
huggingface-cli download MahmoudAshraf/mms-300m-1130-forced-aligner --local-dir models\mms-300m-1130-forced-aligner
```

---

## Source Distribution

When distributing the source code, do not include the following:

* `.venv`
* `build`
* `dist`
* Generated `.lrc` files
* Model files
* Copyrighted audio files

Run:

```
.\make_source_zip.ps1
```

This creates:

```
CTCLRC-source.zip
```
