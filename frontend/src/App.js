import React, { useState } from "react";

const BACKEND_URL = "https://fast-api-dep.onrender.com"; // Replace with actual backend URL

function App() {
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [processingResult, setProcessingResult] = useState([]);
    const [loading, setLoading] = useState(false);
    const [imagePath, setImagePath] = useState(""); // Store the image path

    // Handle file selection
    const handleFileChange = (event) => {
        setSelectedFiles(event.target.files);
    };

    // Upload and Process files together
    const handleUploadAndProcess = async () => {
        if (selectedFiles.length === 0) {
            alert("Please select a folder to upload.");
            return;
        }

        setLoading(true);
        setProcessingResult([]); // Reset results before processing
        setImagePath(""); // Reset image path

        const formData = new FormData();
        for (let i = 0; i < selectedFiles.length; i++) {
            formData.append("files", selectedFiles[i]); // Append each file
        }

        try {
            // Step 1: Upload files
            const uploadResponse = await fetch(`${BACKEND_URL}/upload-folder/`, {
                method: "POST",
                body: formData,
            });

            if (!uploadResponse.ok) {
                throw new Error("File upload failed.");
            }

            // Step 2: Process folder after upload
            const processResponse = await fetch(`${BACKEND_URL}/process-folder/`, {
                method: "POST",
            });

            if (!processResponse.ok) {
                throw new Error("Processing failed.");
            }

            const data = await processResponse.json();
            setProcessingResult(data.results);
            setImagePath(`${BACKEND_URL}/roi_overlay.png`); // Assuming the image is saved as "roi_overlay.png" in the backend
            alert("Processing completed successfully!");

        } catch (error) {
            console.error("Error:", error);
            alert("An error occurred. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100vh",
            width: "100vw",
            fontFamily: "Arial, sans-serif",
            backgroundColor: "#f9f9f9"
        }}>
            <h1 style={{ color: "#333", marginBottom: "20px" }}>MRI DICOM Analysis</h1>

            {/* File Input */}
            <input 
                type="file" 
                webkitdirectory="" 
                directory="" 
                multiple 
                onChange={handleFileChange} 
                style={{
                    padding: "10px",
                    border: "1px solid #ccc",
                    borderRadius: "5px",
                    display: "block",
                    marginBottom: "20px"
                }}
            />

            {/* Upload & Process Button */}
            <button 
                onClick={handleUploadAndProcess} 
                disabled={loading}
                style={{
                    padding: "12px 24px",
                    fontSize: "16px",
                    color: "white",
                    backgroundColor: loading ? "#999" : "#007BFF",
                    border: "none",
                    borderRadius: "5px",
                    cursor: loading ? "not-allowed" : "pointer",
                    marginBottom: "20px"
                }}
            >
                {loading ? "Processing..." : "Upload & Process"}
            </button>

            {/* Display ROI Overlay Image */}
            {imagePath && (
                <div style={{ marginBottom: "20px" }}>
                    <h2>ROI Overlay Image</h2>
                    <img 
                        src={imagePath} 
                        alt="ROI Overlay" 
                        style={{ width: "500px", borderRadius: "5px", border: "1px solid #ccc" }}
                    />
                </div>
            )}

            {/* Processing Results */}
            {processingResult.length > 0 && (
                <div style={{
                    width: "90%",
                    backgroundColor: "white",
                    padding: "20px",
                    borderRadius: "5px",
                    boxShadow: "0px 2px 5px rgba(0, 0, 0, 0.1)",
                    overflowX: "auto"
                }}>
                    <h2 style={{ textAlign: "center", color: "#333" }}>Processing Results</h2>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                        <thead>
                            <tr style={{ backgroundColor: "#007BFF", color: "white", textAlign: "center" }}>
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
                                <tr key={index} style={{ textAlign: "center", borderBottom: "1px solid #ddd" }}>
                                    <td>{row.Filename}</td>
                                    <td>{parseFloat(row.Mean).toFixed(2)}</td>
                                    <td>{parseFloat(row.Min).toFixed(2)}</td>
                                    <td>{parseFloat(row.Max).toFixed(2)}</td>
                                    <td>{parseFloat(row.Sum).toFixed(2)}</td>
                                    <td>{parseFloat(row.StDev).toFixed(2)}</td>
                                    <td>{parseFloat(row.SNR).toFixed(2)}</td>
                                    <td>{parseFloat(row.PIU).toFixed(2)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

export default App;
