import flet as ft
import threading
import requests
import os
import json
import pandas as pd
from pathlib import Path
import time
import subprocess

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
        def run_backend():
            try:
                server_thread, actual_port = self.backend.start_server()
                self.backend_url = f"http://127.0.0.1:{actual_port}"
                time.sleep(2)
                self.server_running = True
                print(f"Backend server started on port {actual_port}")
            except Exception as e:
                print(f"Failed to start backend: {e}")
                self.server_running = False
        
        backend_thread = threading.Thread(target=run_backend, daemon=True)
        backend_thread.start()
        
        for _ in range(10):
            try:
                response = requests.get(f"{self.backend_url}/", timeout=1)
                self.server_running = True
                break
            except Exception:
                time.sleep(1)
    
    def pick_folder(self, e):
        def _open_dialog():
            try:
                result = subprocess.run(
                    ["osascript", "-e",
                     'POSIX path of (choose folder with prompt "Select DICOM Folder")'],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    folder = result.stdout.strip().rstrip("/")
                    if folder:
                        self.selected_folder = folder
                        self.folder_text.value = folder
                        if self.page:
                            self.page.update()
            except Exception as ex:
                print(f"Folder picker error: {ex}")
        threading.Thread(target=_open_dialog, daemon=True).start()
    
    def clear_previous_results(self):
        self.weekly_results = None
        self.nema_results = None
        self.torso_results = None
        self.headneck_results = None
        if self.results_container:
            self.results_container.controls.clear()
            if self.page:
                self.page.update()
    
    def upload_files(self, folder_path):
        self.clear_previous_results()
        files = []
        for root, _, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(file_path, folder_path)
                files.append(('files', (relative_path, open(file_path, 'rb'))))
        response = requests.post(f"{self.backend_url}/upload-folder/", files=files)
        for _, (_, file_obj) in files:
            file_obj.close()
        return response.json()
    
    def process_weekly(self, e):
        if not self.selected_folder:
            return
        def process_thread():
            try:
                self.weekly_btn.disabled = True
                self.weekly_btn.text = "Processing..."
                if self.page:
                    self.page.update()
                self.upload_files(self.selected_folder)
                response = requests.post(f"{self.backend_url}/process-folder/", timeout=300)
                if response.status_code == 200:
                    result = response.json()
                    self.weekly_results = result.get('results', [])
                else:
                    self.weekly_results = []
                self.update_results_display()
            except Exception as ex:
                print(f"Error: {ex}")
            finally:
                self.weekly_btn.disabled = False
                self.weekly_btn.text = "Process Weekly"
                if self.page:
                    self.page.update()
        threading.Thread(target=process_thread, daemon=True).start()
    
    def process_nema(self, e):
        if not self.selected_folder:
            return
        def process_thread():
            try:
                self.nema_btn.disabled = True
                self.nema_btn.text = "Processing..."
                if self.page:
                    self.page.update()
                self.upload_files(self.selected_folder)
                response = requests.post(f"{self.backend_url}/process-nema-body/", timeout=300)
                if response.status_code == 200:
                    result = response.json()
                    self.nema_results = result.get('results', {})
                else:
                    self.nema_results = {}
                self.update_results_display()
            except Exception as ex:
                print(f"Error: {ex}")
            finally:
                self.nema_btn.disabled = False
                self.nema_btn.text = "Process NEMA Body"
                if self.page:
                    self.page.update()
        threading.Thread(target=process_thread, daemon=True).start()
    
    def process_torso(self, e):
        if not self.selected_folder:
            return
        def process_thread():
            try:
                self.torso_btn.disabled = True
                self.torso_btn.text = "Processing..."
                if self.page:
                    self.page.update()
                self.upload_files(self.selected_folder)
                response = requests.post(f"{self.backend_url}/process-torso/", timeout=300)
                if response.status_code == 200:
                    self.torso_results = response.json()
                else:
                    self.torso_results = {'combined_results': [], 'element_results': []}
                self.update_results_display()
            except Exception as ex:
                print(f"Error: {ex}")
            finally:
                self.torso_btn.disabled = False
                self.torso_btn.text = "Process Torso"
                if self.page:
                    self.page.update()
        threading.Thread(target=process_thread, daemon=True).start()
    
    def process_head_neck(self, e):
        if not self.selected_folder:
            return
        def process_thread():
            try:
                self.head_neck_btn.disabled = True
                self.head_neck_btn.text = "Processing..."
                if self.page:
                    self.page.update()
                self.upload_files(self.selected_folder)
                response = requests.post(f"{self.backend_url}/process-head-neck/", timeout=300)
                if response.status_code == 200:
                    self.headneck_results = response.json()
                else:
                    self.headneck_results = {'combined_results': [], 'element_results': []}
                self.update_results_display()
            except Exception as ex:
                print(f"Error: {ex}")
            finally:
                self.head_neck_btn.disabled = False
                self.head_neck_btn.text = "Process Head and Neck"
                if self.page:
                    self.page.update()
        threading.Thread(target=process_thread, daemon=True).start()
    
    def create_table(self, data, headers, title, bgcolor="#1976d2"):
        if not data:
            return ft.Container()
        header_cells = [ft.DataCell(ft.Text(h, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)) for h in headers]
        header_row = ft.DataRow(cells=header_cells, color=bgcolor)
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
            ft.Text(title, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
            ft.DataTable(
                columns=[ft.DataColumn(ft.Text("")) for _ in headers],
                rows=rows,
                border=ft.Border.all(1, ft.Colors.GREY_400),
                bgcolor=ft.Colors.WHITE,
                heading_row_color=bgcolor,
            )
        ], spacing=10)
    
    def download_weekly_results(self, e):
        try:
            response = requests.get(f"{self.backend_url}/download-metrics", timeout=30)
            if response.status_code == 200:
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                file_path = os.path.join(downloads_path, "weekly_metrics.xlsx")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"Weekly results downloaded to: {file_path}")
        except Exception as ex:
            print(f"Download error: {ex}")
    
    def download_nema_results(self, e):
        try:
            response = requests.get(f"{self.backend_url}/download-nema-body", timeout=30)
            if response.status_code == 200:
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                file_path = os.path.join(downloads_path, "nema_body_metrics.xlsx")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"NEMA body results downloaded to: {file_path}")
        except Exception as ex:
            print(f"Download error: {ex}")
    
    def download_torso_results(self, e):
        try:
            response = requests.get(f"{self.backend_url}/download-torso", timeout=30)
            if response.status_code == 200:
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                file_path = os.path.join(downloads_path, "torso_coil_analysis.xlsx")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"Torso results downloaded to: {file_path}")
        except Exception as ex:
            print(f"Download error: {ex}")
    
    def download_headneck_results(self, e):
        try:
            response = requests.get(f"{self.backend_url}/download-head-neck", timeout=30)
            if response.status_code == 200:
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                file_path = os.path.join(downloads_path, "headneck_analysis.xlsx")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"Head & Neck results downloaded to: {file_path}")
        except Exception as ex:
            print(f"Download error: {ex}")
    
    def open_output_folder(self, e):
        try:
            response = requests.get(f"{self.backend_url}/output-folder-path", timeout=10)
            if response.status_code == 200:
                folder_info = response.json()
                folder_path = folder_info.get("path")
                if folder_path and folder_info.get("exists", False):
                    print(f"Output folder is located at: {folder_path}")
                else:
                    print("Output folder does not exist yet.")
        except Exception as ex:
            print(f"Error retrieving folder info: {str(ex)}")

    def update_results_display(self):
        if not self.results_container:
            return
        self.results_container.controls.clear()
        
        if self.weekly_results is not None:
            if self.weekly_results:
                table = self.create_table(
                    self.weekly_results,
                    ["Filename", "Mean", "Min", "Max", "Sum", "StDev", "SNR", "PIU"],
                    "Weekly Processing Results",
                    ft.Colors.BLUE_600
                )
                self.results_container.controls.append(table)
            else:
                self.results_container.controls.append(
                    ft.Text("Weekly Processing: No valid DICOM files found",
                           size=16, color=ft.Colors.ORANGE_600, weight=ft.FontWeight.BOLD)
                )
            self.results_container.controls.append(
                ft.Button("Download Weekly Results", icon="download",
                         on_click=self.download_weekly_results,
                         style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE))
            )
        
        if self.nema_results is not None:
            if self.nema_results:
                for group_name, group_data in self.nema_results.items():
                    if group_data:
                        table = self.create_table(
                            group_data,
                            ["Orientation", "Type", "Mean", "Min", "Max", "Sum", "StDev", "SNR", "PIU"],
                            f"NEMA Body Results - {group_name}",
                            ft.Colors.PURPLE_600
                        )
                        self.results_container.controls.append(table)
                if not any(self.nema_results.values()):
                    self.results_container.controls.append(
                        ft.Text("NEMA Body Processing: No valid DICOM image files found",
                               size=16, color=ft.Colors.ORANGE_600, weight=ft.FontWeight.BOLD)
                    )
            else:
                self.results_container.controls.append(
                    ft.Text("NEMA Body Processing: No valid DICOM image files found",
                           size=16, color=ft.Colors.ORANGE_600, weight=ft.FontWeight.BOLD)
                )
            self.results_container.controls.append(
                ft.Button("Download NEMA Body Results", icon="download",
                         on_click=self.download_nema_results,
                         style=ft.ButtonStyle(bgcolor=ft.Colors.PURPLE_600, color=ft.Colors.WHITE))
            )
        
        if self.torso_results is not None:
            has_results = False
            if self.torso_results.get('combined_results'):
                table = self.create_table(
                    self.torso_results['combined_results'],
                    ["Region", "Signal Max", "Signal Min", "Signal Mean", "Noise SD", "SNR", "Uniformity"],
                    "Torso Results - Combined Views",
                    ft.Colors.GREEN_600
                )
                self.results_container.controls.append(table)
                has_results = True
            if self.torso_results.get('element_results'):
                table = self.create_table(
                    self.torso_results['element_results'],
                    ["Element", "Signal Mean", "Noise SD", "SNR"],
                    "Torso Results - Individual Elements",
                    ft.Colors.GREEN_600
                )
                self.results_container.controls.append(table)
                has_results = True
            if not has_results:
                self.results_container.controls.append(
                    ft.Text("Torso Processing: No valid DICOM files found",
                           size=16, color=ft.Colors.ORANGE_600, weight=ft.FontWeight.BOLD)
                )
            self.results_container.controls.append(
                ft.Button("Download Torso Results", icon="download",
                         on_click=self.download_torso_results,
                         style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE))
            )
        
        if self.headneck_results is not None:
            has_results = False
            if self.headneck_results.get('combined_results'):
                table = self.create_table(
                    self.headneck_results['combined_results'],
                    ["Region", "Signal Max", "Signal Min", "Signal Mean", "Noise SD", "SNR", "Uniformity"],
                    "Head & Neck Results - Combined Views",
                    ft.Colors.ORANGE_600
                )
                self.results_container.controls.append(table)
                has_results = True
            if self.headneck_results.get('element_results'):
                table = self.create_table(
                    self.headneck_results['element_results'],
                    ["Element", "Signal Mean", "Noise SD", "SNR"],
                    "Head & Neck Results - Individual Elements",
                    ft.Colors.ORANGE_600
                )
                self.results_container.controls.append(table)
                has_results = True
            if not has_results:
                self.results_container.controls.append(
                    ft.Text("Head & Neck Processing: No valid DICOM files found",
                           size=16, color=ft.Colors.ORANGE_600, weight=ft.FontWeight.BOLD)
                )
            self.results_container.controls.append(
                ft.Button("Download Head & Neck Results", icon="download",
                         on_click=self.download_headneck_results,
                         style=ft.ButtonStyle(bgcolor=ft.Colors.ORANGE_600, color=ft.Colors.WHITE))
            )
        
        if (self.weekly_results is not None or
            self.nema_results is not None or
            self.torso_results is not None or
            self.headneck_results is not None):
            self.results_container.controls.append(
                ft.Container(
                    content=ft.Button("Open Output Folder", icon="folder_open",
                                     on_click=self.open_output_folder,
                                     style=ft.ButtonStyle(bgcolor=ft.Colors.AMBER_600, color=ft.Colors.WHITE)),
                    margin=ft.Margin.only(top=20)
                )
            )
        
        if self.page:
            self.page.update()
    
    def main(self, page: ft.Page):
        self.page = page
        page.title = "MRI DICOM Analysis"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 20
        page.bgcolor = ft.Colors.GREY_100
        try:
            page.window.width = 1200
            page.window.height = 800
            page.window.resizable = True
        except AttributeError:
            pass
        
        self.folder_text = ft.Text("No folder selected", size=14, color=ft.Colors.GREY_600)
        
        self.weekly_btn = ft.Button(
            "Process Weekly", on_click=self.process_weekly,
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE),
            width=200, height=50
        )
        self.nema_btn = ft.Button(
            "Process NEMA Body", on_click=self.process_nema,
            style=ft.ButtonStyle(bgcolor=ft.Colors.PURPLE_600, color=ft.Colors.WHITE),
            width=200, height=50
        )
        self.torso_btn = ft.Button(
            "Process Torso", on_click=self.process_torso,
            style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE),
            width=200, height=50
        )
        self.head_neck_btn = ft.Button(
            "Process Head and Neck", on_click=self.process_head_neck,
            style=ft.ButtonStyle(bgcolor=ft.Colors.ORANGE_600, color=ft.Colors.WHITE),
            width=200, height=50
        )
        
        self.results_container = ft.Column(spacing=20, scroll=ft.ScrollMode.AUTO, expand=True)
        
        page.add(
            ft.Column([
                ft.Text("MRI DICOM Analysis", size=32, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLACK, text_align=ft.TextAlign.CENTER),
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Button("Browse Folder", icon="folder_open",
                                     on_click=self.pick_folder,
                                     style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE)),
                            ft.Container(content=self.folder_text, expand=True, padding=10)
                        ])
                    ]),
                    bgcolor=ft.Colors.WHITE, padding=20, border_radius=10,
                    margin=ft.Margin.only(bottom=20)
                ),
                ft.Container(
                    content=ft.Row([
                        self.weekly_btn, self.nema_btn, self.torso_btn, self.head_neck_btn
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                    margin=ft.Margin.only(bottom=20)
                ),
                ft.Container(
                    content=self.results_container,
                    bgcolor=ft.Colors.WHITE, padding=20, border_radius=10, expand=True
                )
            ], spacing=0, expand=True)
        )

def main():
    from desktop_backend import backend
    app = MRIAnalysisApp(backend)
    ft.run(app.main, view=ft.AppView.FLET_APP)

if __name__ == "__main__":
    main()
