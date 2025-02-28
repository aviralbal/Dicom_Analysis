import React, { useState } from "react";

const BACKEND_URL = "https://fast-api-dep.onrender.com"; // Replace with actual backend URL

function App() {
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [processingResult, setProcessingResult] = useState([]);

    const handleFileChange = (event) => {
        setSelectedFiles(event.target.files);
    };

    const handleUpload = async () => {
        if (selectedFiles.length === 0) {
            alert("Please select a folder to upload.");
            return;
        }

        const formData = new FormData();
        for (let i = 0; i < selectedFiles.length; i++) {
            formData.append("files", selectedFiles[i]); // Append each file
        }

        try {
            const response = await fetch(`${BACKEND_URL}/upload-folder/`, {
                method: "POST",
                body: formData,
            });

            if (response.ok) {
                alert("Folder uploaded successfully!");
            } else {
                alert("Upload failed.");
            }
        } catch (error) {
            console.error("Upload error:", error);
        }
    };

    const handleProcess = async () => {
        try {
            const response = await fetch(`${BACKEND_URL}/process-folder/`, {
                method: "POST",
            });

            const data = await response.json();
            setProcessingResult(data.results);
        } catch (error) {
            console.error("Processing error:", error);
            setProcessingResult([]);
        }
    };

    return (
        <div style={{ textAlign: "center", padding: "50px" }}>
            <h1>MRI DICOM Analysis</h1>
            <input type="file" webkitdirectory="" directory="" multiple onChange={handleFileChange} />
            <button onClick={handleUpload}>Upload Folder</button>
            <button onClick={handleProcess}>Process Folder</button>

            <h2>Processing Results:</h2>
            {processingResult.length > 0 ? (
                <table border="1" style={{ margin: "auto", width: "80%" }}>
                    <thead>
                        <tr>
                            <th>Filename</th>
                            <th>Mean</th>
                            <th>Min</th>
                            <th>Max</th>
                            <th>Sum</th>
                            <th>StDev</th>
                            <th>SNR</th>
                            <th>PIU</th>
                        </tr>
                    </thead>
                    <tbody>
                        {processingResult.map((row, index) => (
                            <tr key={index}>
                                <td>{row.Filename}</td>
                                <td>{row.Mean}</td>
                                <td>{row.Min}</td>
                                <td>{row.Max}</td>
                                <td>{row.Sum}</td>
                                <td>{row.StDev}</td>
                                <td>{row.SNR}</td>
                                <td>{row.PIU}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            ) : (
                <p>No results yet.</p>
            )}
        </div>
    );
}

export default App;
