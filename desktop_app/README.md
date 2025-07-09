# MRI DICOM Analysis Desktop Application

A modern desktop application for analyzing MRI DICOM files with support for Weekly, NEMA Body, and Torso analysis.

## Features

- **Modern GUI**: Built with Flet (Flutter for Python) for a beautiful, Material Design interface
- **Three Analysis Types**:
  - Weekly Processing
  - NEMA Body Analysis
  - Torso Coil Analysis
- **Embedded Backend**: FastAPI server runs locally within the app
- **Real-time Progress**: Visual progress tracking and status updates
- **Export Results**: Download Excel files and view ROI images
- **Cross-platform**: Works on Windows, macOS, and Linux

## Quick Start

### Option 1: Run from Source (Recommended for Development)

1. **Install Python 3.8 or later**

2. **Clone/Download this folder**

3. **Install Dependencies**:
   ```bash
   cd desktop_app
   pip install -r requirements.txt
   ```

4. **Run the Application**:
   ```bash
   python main.py
   ```

### Option 2: Build Standalone Executable

1. **Install Dependencies** (including PyInstaller):
   ```bash
   pip install -r requirements.txt
   ```

2. **Build the Executable**:
   ```bash
   python build_app.py
   ```

3. **Run the Executable**:
   - Navigate to the `dist` folder
   - Double-click `MRI_DICOM_Analysis.exe` (Windows) or equivalent

## How to Use

1. **Start the Application**
   - The backend server will automatically start
   - Wait for "Backend Server Running - Ready" status

2. **Select DICOM Folder**
   - Click "Browse Folder"
   - Select your folder containing DICOM files

3. **Choose Analysis Type**
   - **Process Weekly**: Standard weekly analysis
   - **Process NEMA Body**: NEMA body phantom analysis
   - **Process Torso**: Torso coil analysis

4. **View Results**
   - Results appear in the text area
   - Download Excel files using "Download Excel" button
   - View ROI images (when available) using "View ROI Image"
   - Open output folder to see all generated files

## System Requirements

### Minimum Requirements
- **OS**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space
- **Python**: 3.8+ (if running from source)

### Recommended Specifications
- **RAM**: 16GB for large DICOM datasets
- **CPU**: Multi-core processor for faster processing
- **Storage**: SSD for better I/O performance

## File Structure

```
desktop_app/
├── main.py                 # Main entry point
├── desktop_backend.py      # FastAPI backend server
├── desktop_gui.py          # CustomTkinter GUI
├── script.py              # Weekly analysis script
├── nema_body.py           # NEMA body analysis script
├── torso.py               # Torso analysis script
├── build_app.py           # PyInstaller build script
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── uploads/               # Temporary upload folder (auto-created)
├── outputs/               # Analysis results (auto-created)
└── app.log               # Application logs (auto-created)
```

## Troubleshooting

### Common Issues

1. **"Backend Server Failed to Start"**
   - Ensure port 8000 is not in use by another application
   - Check firewall settings
   - Restart the application

2. **"No files found in uploads directory"**
   - Ensure your folder contains DICOM files (.IMA or .dcm files)
   - Check that the folder is not empty
   - Verify file permissions

3. **Processing Errors**
   - Check that DICOM files are valid and readable
   - Ensure sufficient disk space for outputs
   - Review `app.log` file for detailed error messages

4. **Installation Issues**
   - Use Python 3.8-3.11 (avoid 3.12+ for better compatibility)
   - Consider using a virtual environment:
     ```bash
     python -m venv venv
     source venv/bin/activate  # On Windows: venv\Scripts\activate
     pip install -r requirements.txt
     ```

### Performance Tips

- **For Large Datasets**: Increase available RAM
- **Slow Processing**: Close other applications to free up CPU
- **Storage Issues**: Regularly clean the `outputs` folder

## Dependencies

- **FastAPI**: Web framework for the backend API
- **Flet**: Modern GUI framework based on Flutter
- **PyInstaller**: For building standalone executables
- **Pandas**: Data manipulation and analysis
- **NumPy**: Numerical computing
- **PyDICOM**: DICOM file reading and processing
- **Scikit-image**: Image processing
- **Matplotlib**: Plotting and visualization
- **OpenPyXL**: Excel file generation

## Building for Distribution

To create a standalone executable that can run on any computer without Python installed:

1. **Install build dependencies**:
   ```bash
   pip install pyinstaller
   ```

2. **Run the build script**:
   ```bash
   python build_app.py
   ```

3. **Distribute**:
   - The executable will be in the `dist` folder
   - Copy the entire `dist` folder to the target computer
   - No Python installation required on the target computer

## License

This application is provided as-is for medical imaging analysis purposes.

## Support

For issues or questions:
1. Check the `app.log` file for detailed error messages
2. Ensure all dependencies are properly installed
3. Verify that your DICOM files are valid and readable

---

**Note**: This application processes medical imaging data. Ensure compliance with your institution's data handling policies and regulations. 