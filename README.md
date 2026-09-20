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
1. Launch the application.
2. Set generation parameters (Language, by-line/charsync, embed)
3. Configure if the application should check LRClib for existing lyrics
4. Hit `generate`
5. Once generated, use `View lyrics` button to check if the timings are correct. If not, you can edit the timings.
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
dist\CTCLRC.exe
```

## Important Distribution Notes

Builds should use the **single-file (One-File)** PyInstaller specification:

```
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm CTCLRC.spec
```

Output:

```
dist\CTCLRC.exe
```

The generated executable is a single standalone file.

Users can move `CTCLRC.exe` to any folder and run it directly.

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
