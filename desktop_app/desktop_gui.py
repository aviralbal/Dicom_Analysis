import flet as ft
import threading
import requests
import os
import json
import pandas as pd
from pathlib import Path
import time

class MRIAnalysisApp:
    def __init__(self, backend):
        self.backend = backend
        self.backend_url = "http://127.0.0.1:8000"
        self.server_running = False
        self.selected_folder = None
        
        # Results storage
        self.weekly_results = []
        self.nema_results = {}
        self.torso_results = {}
        self.headneck_results = {}
        
        # UI components
        self.page = None
        self.folder_text = None
        self.weekly_btn = None
        self.nema_btn = None
        self.torso_btn = None
        self.head_neck_btn = None
        self.results_container = None
        
        # Start backend server
        self.start_backend()
    
    def start_backend(self):
        """Start the backend server in a separate thread."""
        def run_backend():
            try:
                server_thread, actual_port = self.backend.start_server()
                self.backend_url = f"http://127.0.0.1:{actual_port}"
                time.sleep(2)  # Give server time to start
                self.server_running = True
                print(f"Backend server started on port {actual_port}")
            except Exception as e:
                print(f"Failed to start backend: {e}")
                self.server_running = False
        
        backend_thread = threading.Thread(target=run_backend, daemon=True)
        backend_thread.start()
        
        # Wait for server to start
        for _ in range(10):
            try:
                response = requests.get(f"{self.backend_url}/", timeout=1)
                self.server_running = True
                break
            except:
                time.sleep(1)
    
    def pick_folder(self, e):
        """Handle folder selection."""
        def get_directory_result(e: ft.FilePickerResultEvent):
            if e.path:
                self.selected_folder = e.path
                self.folder_text.value = e.path
                if self.page:
                    self.page.update()
        
        file_picker = ft.FilePicker(on_result=get_directory_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.get_directory_path()
    
    def clear_previous_results(self):
        """Clear all previous results."""
        self.weekly_results = None
        self.nema_results = None
        self.torso_results = None
        self.headneck_results = None
        # Clear the results display
        if self.results_container:
            self.results_container.controls.clear()
            if self.page:
                self.page.update()
    
    def upload_files(self, folder_path):
        """Upload files to backend while preserving folder structure."""
        # Clear previous results when uploading new files
        self.clear_previous_results()
        
        files = []
        for root, _, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                # Calculate relative path to preserve folder structure
                relative_path = os.path.relpath(file_path, folder_path)
                files.append(('files', (relative_path, open(file_path, 'rb'))))
        
        response = requests.post(f"{self.backend_url}/upload-folder/", files=files)
        for _, (_, file_obj) in files:
            file_obj.close()
        return response.json()
    
    def process_weekly(self, e):
        """Process weekly analysis."""
        if not self.selected_folder:
            return
        
        def process_thread():
            try:
                # Disable button
                self.weekly_btn.disabled = True
                self.weekly_btn.text = "Processing..."
                if self.page:
                    self.page.update()
                
                # Upload and process
                self.upload_files(self.selected_folder)
                response = requests.post(f"{self.backend_url}/process-folder/", timeout=300)
                
                if response.status_code == 200:
                    result = response.json()
                    # Store results and update UI
                    self.weekly_results = result.get('results', [])
                else:
                    # Handle error but still show empty results with download option
                    self.weekly_results = []
                    print(f"Processing failed with status {response.status_code}: {response.text}")
                
                self.update_results_display()
                
            except Exception as e:
                print(f"Error: {e}")
            finally:
                # Re-enable button
                self.weekly_btn.disabled = False
                self.weekly_btn.text = "Process Weekly"
                if self.page:
                    self.page.update()
        
        thread = threading.Thread(target=process_thread, daemon=True)
        thread.start()
    
    def process_nema(self, e):
        """Process NEMA body analysis."""
        if not self.selected_folder:
            return
        
        def process_thread():
            try:
                # Disable button
                self.nema_btn.disabled = True
                self.nema_btn.text = "Processing..."
                if self.page:
                    self.page.update()
                
                # Upload and process
                self.upload_files(self.selected_folder)
                response = requests.post(f"{self.backend_url}/process-nema-body/", timeout=300)
                
                if response.status_code == 200:
                    result = response.json()
                    # Store results and update UI
                    self.nema_results = result.get('results', {})
                else:
                    # Handle error but still show empty results with download option
                    self.nema_results = {}
                    print(f"Processing failed with status {response.status_code}: {response.text}")
                
                self.update_results_display()
                
            except Exception as e:
                print(f"Error: {e}")
            finally:
                # Re-enable button
                self.nema_btn.disabled = False
                self.nema_btn.text = "Process NEMA Body"
                if self.page:
                    self.page.update()
        
        thread = threading.Thread(target=process_thread, daemon=True)
        thread.start()
    
    def process_torso(self, e):
        """Process torso analysis."""
        if not self.selected_folder:
            return
        
        def process_thread():
            try:
                # Disable button
                self.torso_btn.disabled = True
                self.torso_btn.text = "Processing..."
                if self.page:
                    self.page.update()
                
                # Upload and process
                self.upload_files(self.selected_folder)
                response = requests.post(f"{self.backend_url}/process-torso/", timeout=300)
                
                if response.status_code == 200:
                    result = response.json()
                    # Store results and update UI
                    self.torso_results = result
                else:
                    # Handle error but still show empty results with download option
                    self.torso_results = {'combined_results': [], 'element_results': []}
                    print(f"Processing failed with status {response.status_code}: {response.text}")
                
                self.update_results_display()
                
            except Exception as e:
                print(f"Error: {e}")
            finally:
                # Re-enable button
                self.torso_btn.disabled = False
                self.torso_btn.text = "Process Torso"
                if self.page:
                    self.page.update()
        
        thread = threading.Thread(target=process_thread, daemon=True)
        thread.start()
    
    def process_head_neck(self, e):
        """Process head and neck analysis."""
        if not self.selected_folder:
            return
        
        def process_thread():
            try:
                # Disable button
                self.head_neck_btn.disabled = True
                self.head_neck_btn.text = "Processing..."
                if self.page:
                    self.page.update()
                
                # Upload and process
                self.upload_files(self.selected_folder)
                response = requests.post(f"{self.backend_url}/process-head-neck/", timeout=300)
                
                if response.status_code == 200:
                    result = response.json()
                    # Store results and update UI
                    self.headneck_results = result
                else:
                    # Handle error but still show empty results with download option
                    self.headneck_results = {'combined_results': [], 'element_results': []}
                    print(f"Processing failed with status {response.status_code}: {response.text}")
                
                self.update_results_display()
                
            except Exception as e:
                print(f"Error: {e}")
            finally:
                # Re-enable button
                self.head_neck_btn.disabled = False
                self.head_neck_btn.text = "Process Head and Neck"
                if self.page:
                    self.page.update()
        
        thread = threading.Thread(target=process_thread, daemon=True)
        thread.start()
    
    def create_table(self, data, headers, title, bgcolor="#1976d2"):
        """Create a simple data table."""
        if not data:
            return ft.Container()
        
        # Create header row
        header_cells = [ft.DataCell(ft.Text(h, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD)) for h in headers]
        header_row = ft.DataRow(cells=header_cells, color=bgcolor)
        
        # Create data rows
        rows = [header_row]
        for item in data:
            cells = []
            for header in headers:
                value = item.get(header, "")
                if isinstance(value, (int, float)):
                    cells.append(ft.DataCell(ft.Text(f"{value:.2f}" if isinstance(value, float) else str(value))))
                else:
                    cells.append(ft.DataCell(ft.Text(str(value))))
            rows.append(ft.DataRow(cells=cells))
        
        return ft.Column([
            ft.Text(title, size=20, weight=ft.FontWeight.BOLD, color=ft.colors.BLACK),
            ft.DataTable(
                columns=[ft.DataColumn(ft.Text("")) for _ in headers],
                rows=rows,
                border=ft.border.all(1, ft.colors.GREY_400),
                bgcolor=ft.colors.WHITE,
                heading_row_color=bgcolor,
            )
        ], spacing=10)
    
    def download_weekly_results(self, e):
        """Download weekly results."""
        try:
            response = requests.get(f"{self.backend_url}/download-metrics", timeout=30)
            if response.status_code == 200:
                # Save file to Downloads folder
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                file_path = os.path.join(downloads_path, "weekly_metrics.xlsx")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"Weekly results downloaded to: {file_path}")
            else:
                print(f"Download failed: {response.status_code}")
        except Exception as e:
            print(f"Download error: {e}")
    
    def download_nema_results(self, e):
        """Download NEMA body results."""
        try:
            response = requests.get(f"{self.backend_url}/download-nema-body", timeout=30)
            if response.status_code == 200:
                # Save file to Downloads folder
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                file_path = os.path.join(downloads_path, "nema_body_metrics.xlsx")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"NEMA body results downloaded to: {file_path}")
            else:
                print(f"Download failed: {response.status_code}")
        except Exception as e:
            print(f"Download error: {e}")
    
    def download_torso_results(self, e):
        """Download torso results."""
        try:
            response = requests.get(f"{self.backend_url}/download-torso", timeout=30)
            if response.status_code == 200:
                # Save file to Downloads folder
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                file_path = os.path.join(downloads_path, "torso_coil_analysis.xlsx")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"Torso results downloaded to: {file_path}")
            else:
                print(f"Download failed: {response.status_code}")
        except Exception as e:
            print(f"Download error: {e}")
    
    def download_headneck_results(self, e):
        """Download head and neck results."""
        try:
            response = requests.get(f"{self.backend_url}/download-head-neck", timeout=30)
            if response.status_code == 200:
                # Save file to Downloads folder
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                file_path = os.path.join(downloads_path, "headneck_analysis.xlsx")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"Head & Neck results downloaded to: {file_path}")
            else:
                print(f"Download failed: {response.status_code}")
        except Exception as e:
            print(f"Download error: {e}")
    
    def open_output_folder(self, e):
        """Show output folder path instead of opening Finder/Explorer."""
        try:
            response = requests.get(f"{self.backend_url}/output-folder-path", timeout=10)
            if response.status_code == 200:
                folder_info = response.json()
                folder_path = folder_info.get("path")

                if folder_path and folder_info.get("exists", False):
                    print(f"Output folder is located at: {folder_path}")
                else:
                    print("Output folder does not exist yet.")
            else:
                print("Failed to get output folder path.")
        except Exception as ex:
            print(f"Error retrieving folder info: {str(ex)}")

    def update_results_display(self):
        """Update the results display."""
        if not self.results_container:
            return
        
        # Clear existing results
        self.results_container.controls.clear()
        
        # Show weekly results
        if self.weekly_results is not None:
            if self.weekly_results:
                table = self.create_table(
                    self.weekly_results,
                    ["Filename", "Mean", "Min", "Max", "Sum", "StDev", "SNR", "PIU"],
                    "Weekly Processing Results",
                    ft.colors.BLUE_600
                )
                self.results_container.controls.append(table)
            else:
                # Empty results
                self.results_container.controls.append(
                    ft.Text("Weekly Processing: No valid DICOM files found", 
                           size=16, color=ft.colors.ORANGE_600, weight=ft.FontWeight.BOLD)
                )
            
            download_btn = ft.ElevatedButton(
                "Download Weekly Results",
                icon=ft.icons.DOWNLOAD,
                on_click=self.download_weekly_results,
                bgcolor=ft.colors.BLUE_600,
                color=ft.colors.WHITE,
                width=200
            )
            self.results_container.controls.append(download_btn)
        
        # Show NEMA results
        if self.nema_results is not None:
            if self.nema_results:
                for group_name, group_data in self.nema_results.items():
                    if group_data:
                        table = self.create_table(
                            group_data,
                            ["Orientation", "Type", "Mean", "Min", "Max", "Sum", "StDev", "SNR", "PIU"],
                            f"NEMA Body Results - {group_name}",
                            ft.colors.PURPLE_600
                        )
                        self.results_container.controls.append(table)
                
                if not any(self.nema_results.values()):
                    # All groups are empty
                    self.results_container.controls.append(
                        ft.Text("NEMA Body Processing: No valid DICOM image files found", 
                               size=16, color=ft.colors.ORANGE_600, weight=ft.FontWeight.BOLD)
                    )
            else:
                # Empty results
                self.results_container.controls.append(
                    ft.Text("NEMA Body Processing: No valid DICOM image files found", 
                           size=16, color=ft.colors.ORANGE_600, weight=ft.FontWeight.BOLD)
                )
            
            # Add download button for NEMA results (only once after all tables)
            download_btn = ft.ElevatedButton(
                "Download NEMA Body Results",
                icon=ft.icons.DOWNLOAD,
                on_click=self.download_nema_results,
                bgcolor=ft.colors.PURPLE_600,
                color=ft.colors.WHITE,
                width=220
            )
            self.results_container.controls.append(download_btn)
        
        # Show torso results
        if self.torso_results is not None:
            has_results = False
            
            # Combined views
            if self.torso_results.get('combined_results'):
                table = self.create_table(
                    self.torso_results['combined_results'],
                    ["Region", "Signal Max", "Signal Min", "Signal Mean", "Noise SD", "SNR", "Uniformity"],
                    "Torso Results - Combined Views",
                    ft.colors.GREEN_600
                )
                self.results_container.controls.append(table)
                has_results = True
            
            # Individual elements
            if self.torso_results.get('element_results'):
                table = self.create_table(
                    self.torso_results['element_results'],
                    ["Element", "Signal Mean", "Noise SD", "SNR"],
                    "Torso Results - Individual Elements",
                    ft.colors.GREEN_600
                )
                self.results_container.controls.append(table)
                has_results = True
            
            if not has_results:
                self.results_container.controls.append(
                    ft.Text("Torso Processing: No valid DICOM files found", 
                           size=16, color=ft.colors.ORANGE_600, weight=ft.FontWeight.BOLD)
                )
            
            # Add download button for torso results
            download_btn = ft.ElevatedButton(
                "Download Torso Results",
                icon=ft.icons.DOWNLOAD,
                on_click=self.download_torso_results,
                bgcolor=ft.colors.GREEN_600,
                color=ft.colors.WHITE,
                width=200
            )
            self.results_container.controls.append(download_btn)
        
        # Show head & neck results
        if self.headneck_results is not None:
            has_results = False
            
            # Combined views
            if self.headneck_results.get('combined_results'):
                table = self.create_table(
                    self.headneck_results['combined_results'],
                    ["Region", "Signal Max", "Signal Min", "Signal Mean", "Noise SD", "SNR", "Uniformity"],
                    "Head & Neck Results - Combined Views",
                    ft.colors.ORANGE_600
                )
                self.results_container.controls.append(table)
                has_results = True
            
            # Individual elements
            if self.headneck_results.get('element_results'):
                table = self.create_table(
                    self.headneck_results['element_results'],
                    ["Element", "Signal Mean", "Noise SD", "SNR"],
                    "Head & Neck Results - Individual Elements",
                    ft.colors.ORANGE_600
                )
                self.results_container.controls.append(table)
                has_results = True
            
            if not has_results:
                self.results_container.controls.append(
                    ft.Text("Head & Neck Processing: No valid DICOM files found", 
                           size=16, color=ft.colors.ORANGE_600, weight=ft.FontWeight.BOLD)
                )
            
            # Add download button for head & neck results
            download_btn = ft.ElevatedButton(
                "Download Head & Neck Results",
                icon=ft.icons.DOWNLOAD,
                on_click=self.download_headneck_results,
                bgcolor=ft.colors.ORANGE_600,
                color=ft.colors.WHITE,
                width=250
            )
            self.results_container.controls.append(download_btn)
        
        # Add "Open Output Folder" button if any results are shown
        if (self.weekly_results is not None or 
            self.nema_results is not None or 
            self.torso_results is not None or 
            self.headneck_results is not None):
            
            open_folder_btn = ft.ElevatedButton(
                "Open Output Folder",
                icon=ft.icons.FOLDER_OPEN,
                on_click=self.open_output_folder,
                bgcolor=ft.colors.AMBER_600,
                color=ft.colors.WHITE,
                width=200
            )
            self.results_container.controls.append(
                ft.Container(
                    content=open_folder_btn,
                    margin=ft.margin.only(top=20)
                )
            )
        
        if self.page:
            self.page.update()
    
    def main(self, page: ft.Page):
        """Main UI setup."""
        self.page = page
        page.title = "MRI DICOM Analysis"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.window_width = 1200
        page.window_height = 800
        page.window_resizable = True
        page.padding = 20
        page.bgcolor = ft.colors.GREY_100
        
        # Create UI components
        self.folder_text = ft.Text(
            "No folder selected",
            size=14,
            color=ft.colors.GREY_600
        )
        
        self.weekly_btn = ft.ElevatedButton(
            "Process Weekly",
            on_click=self.process_weekly,
            bgcolor=ft.colors.BLUE_600,
            color=ft.colors.WHITE,
            width=200,
            height=50
        )
        
        self.nema_btn = ft.ElevatedButton(
            "Process NEMA Body",
            on_click=self.process_nema,
            bgcolor=ft.colors.PURPLE_600,
            color=ft.colors.WHITE,
            width=200,
            height=50
        )
        
        self.torso_btn = ft.ElevatedButton(
            "Process Torso",
            on_click=self.process_torso,
            bgcolor=ft.colors.GREEN_600,
            color=ft.colors.WHITE,
            width=200,
            height=50
        )
        
        self.head_neck_btn = ft.ElevatedButton(
            "Process Head and Neck",
            on_click=self.process_head_neck,
            bgcolor=ft.colors.ORANGE_600,
            color=ft.colors.WHITE,
            width=200,
            height=50
        )
        
        self.results_container = ft.Column(
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
        
        # Main layout
        page.add(
            ft.Column([
                # Title
                ft.Text(
                    "MRI DICOM Analysis",
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    color=ft.colors.BLACK,
                    text_align=ft.TextAlign.CENTER
                ),
                
                # Folder selection
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.ElevatedButton(
                                "Browse Folder",
                                icon=ft.icons.FOLDER_OPEN,
                                on_click=self.pick_folder,
                                bgcolor=ft.colors.BLUE_600,
                                color=ft.colors.WHITE
                            ),
                            ft.Container(
                                content=self.folder_text,
                                expand=True,
                                padding=10
                            )
                        ])
                    ]),
                    bgcolor=ft.colors.WHITE,
                    padding=20,
                    border_radius=10,
                    margin=ft.margin.only(bottom=20)
                ),
                
                # Process buttons
                ft.Container(
                    content=ft.Row([
                        self.weekly_btn,
                        self.nema_btn,
                        self.torso_btn,
                        self.head_neck_btn
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                    margin=ft.margin.only(bottom=20)
                ),
                
                # Results area
                ft.Container(
                    content=self.results_container,
                    bgcolor=ft.colors.WHITE,
                    padding=20,
                    border_radius=10,
                    expand=True
                )
                
            ], spacing=0, expand=True)
        )

def main():
    # Import here to avoid circular imports
    from desktop_backend import backend
    app = MRIAnalysisApp(backend)
    ft.app(target=main, view=ft.WEB_BROWSER)


if __name__ == "__main__":
    main()
