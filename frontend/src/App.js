import React, { useState } from "react";

const BACKEND_URL = "https://fast-api-dep.onrender.com"; // Backend URL

function App() {
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [processingResult, setProcessingResult] = useState([]);
    const [loading, setLoading] = useState(false);
    const [imagePath, setImagePath] = useState(""); 
    const [excelPath, setExcelPath] = useState(""); 

    const handleFileChange = (event) => {
        setSelectedFiles(event.target.files);
    };

    const handleUploadAndProcess = async () => {
        if (selectedFiles.length === 0) {
            alert("Please select a folder to upload.");
            return;
        }

        setLoading(true);
        setProcessingResult([]);
        setImagePath("");
        setExcelPath("");

        const formData = new FormData();
        for (let i = 0; i < selectedFiles.length; i++) {
            formData.append("files", selectedFiles[i]);
        }

        try {
            await fetch(`${BACKEND_URL}/upload-folder/`, { method: "POST", body: formData });
            const processResponse = await fetch(`${BACKEND_URL}/process-folder/`, { method: "POST" });

            if (!processResponse.ok) throw new Error("Processing failed.");

            const data = await processResponse.json();
            setProcessingResult(data.results);
            if (data.image_url) setImagePath(`${BACKEND_URL}${data.image_url}`);
            if (data.excel_url) setExcelPath(`${BACKEND_URL}${data.excel_url}`);

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
            justifyContent: "flex-start",
            height: "100vh",
            width: "100vw",
            fontFamily: "Arial, sans-serif",
            backgroundColor: "#f4f4f4",
            padding: "30px",
        }}>
            <h1 style={{ color: "#333", marginBottom: "15px", fontSize: "28px", fontWeight: "bold" }}>MRI DICOM Analysis</h1>

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
                    backgroundColor: "white",
                    fontSize: "14px",
                    marginBottom: "10px"
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
                    borderRadius: "8px",
                    cursor: loading ? "not-allowed" : "pointer",
                    marginBottom: "15px",
                    transition: "background 0.3s ease",
                    boxShadow: "0px 4px 8px rgba(0, 123, 255, 0.3)"
                }}
            >
                {loading ? "Processing..." : "Upload & Process"}
            </button>

            {/* Processing Results */}
            {processingResult.length > 0 && (
                <div style={{
                    width: "90%",
                    backgroundColor: "white",
                    padding: "20px",
                    borderRadius: "8px",
                    boxShadow: "0px 4px 8px rgba(0, 0, 0, 0.1)",
                    marginBottom: "15px",
                    textAlign: "center"
                }}>
                    <h2 style={{ textAlign: "center", color: "#333", fontSize: "22px", marginBottom: "10px" }}>Processing Results</h2>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px", tableLayout: "fixed" }}>
                        <thead>
                            <tr style={{ backgroundColor: "#007BFF", color: "white", textAlign: "center" }}>
                                <th style={{ padding: "10px", border: "1px solid #ddd" }}>Filename</th>
                                <th style={{ padding: "10px", border: "1px solid #ddd" }}>Mean</th>
                                <th style={{ padding: "10px", border: "1px solid #ddd" }}>Min</th>
                                <th style={{ padding: "10px", border: "1px solid #ddd" }}>Max</th>
                                <th style={{ padding: "10px", border: "1px solid #ddd" }}>Sum</th>
                                <th style={{ padding: "10px", border: "1px solid #ddd" }}>StDev</th>
                                <th style={{ padding: "10px", border: "1px solid #ddd" }}>SNR</th>
                                <th style={{ padding: "10px", border: "1px solid #ddd" }}>PIU</th>
                            </tr>
                        </thead>
                        <tbody>
                            {processingResult.map((row, index) => (
                                <tr key={index} style={{ textAlign: "center", borderBottom: "1px solid #ddd" }}>
                                    <td style={{ padding: "10px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{row.Filename}</td>
                                    <td style={{ padding: "10px" }}>{parseFloat(row.Mean).toFixed(2)}</td>
                                    <td style={{ padding: "10px" }}>{parseFloat(row.Min).toFixed(2)}</td>
                                    <td style={{ padding: "10px" }}>{parseFloat(row.Max).toFixed(2)}</td>
                                    <td style={{ padding: "10px" }}>{parseFloat(row.Sum).toFixed(2)}</td>
                                    <td style={{ padding: "10px" }}>{parseFloat(row.StDev).toFixed(2)}</td>
                                    <td style={{ padding: "10px" }}>{parseFloat(row.SNR).toFixed(2)}</td>
                                    <td style={{ padding: "10px" }}>{parseFloat(row.PIU).toFixed(2)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Display ROI Overlay Image (Smaller) */}
            {imagePath && (
                <div style={{ marginBottom: "10px", textAlign: "center" }}>
                    <h2 style={{ color: "#333", fontSize: "18px", marginBottom: "5px" }}>ROI Overlay</h2>
                    <img 
                        src={imagePath} 
                        alt="ROI Overlay" 
                        style={{ width: "250px", borderRadius: "5px", border: "1px solid #007BFF" }}
                    />
                </div>
            )}

            {/* Download Buttons */}
            {processingResult.length > 0 && (
                <div style={{ display: "flex", gap: "10px" }}>
                    <a href={excelPath} download>
                        <button style={{ padding: "10px 16px", fontSize: "14px", backgroundColor: "#28a745", color: "white", border: "none", borderRadius: "6px", cursor: "pointer" }}>
                            📊 Download Metrics
                        </button>
                    </a>
                    <a href={imagePath} download>
                        <button style={{ padding: "10px 16px", fontSize: "14px", backgroundColor: "#dc3545", color: "white", border: "none", borderRadius: "6px", cursor: "pointer" }}>
                            🖼️ Download ROI
                        </button>
                    </a>
                </div>
            )}
        </div>
    );
}

export default App;
