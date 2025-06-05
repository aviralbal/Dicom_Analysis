import React, { useState } from "react";

const BACKEND_URL = "https://fast-api-dep.onrender.com"; // Backend URL

function App() {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [processingResult, setProcessingResult] = useState([]);
  const [nemaResult, setNemaResult] = useState(null);
  const [torsoResult, setTorsoResult] = useState(null);
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
    setNemaResult(null);
    setTorsoResult(null);
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

  const handleProcessNemaBody = async () => {
    if (selectedFiles.length === 0) {
      alert("Please select a folder to upload.");
      return;
    }
    setLoading(true);
    setNemaResult(null);
    setTorsoResult(null);
    setImagePath("");
    setExcelPath("");
    const formData = new FormData();
    for (let i = 0; i < selectedFiles.length; i++) {
      formData.append("files", selectedFiles[i]);
    }
    try {
      // First, upload the folder
      await fetch(`${BACKEND_URL}/upload-folder/`, { method: "POST", body: formData });
      // Then, process it with the NEMA body script
      const response = await fetch(`${BACKEND_URL}/process-nema-body/`, { method: "POST" });
      if (!response.ok) throw new Error("NEMA Body Processing failed.");
      const data = await response.json();
      setNemaResult(data.results);
      alert("NEMA Body processing completed successfully!");
    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred during NEMA Body processing. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleProcessTorso = async () => {
    if (selectedFiles.length === 0) {
      alert("Please select a folder to upload.");
      return;
    }
    setLoading(true);
    setNemaResult(null);
    setTorsoResult(null);
    setImagePath("");
    setExcelPath("");
    const formData = new FormData();
    for (let i = 0; i < selectedFiles.length; i++) {
      formData.append("files", selectedFiles[i]);
    }
    try {
      // First, upload the folder
      await fetch(`${BACKEND_URL}/upload-folder/`, { method: "POST", body: formData });
      // Then, process it with the Torso script
      const response = await fetch(`${BACKEND_URL}/process-torso/`, { method: "POST" });
      if (!response.ok) throw new Error("Torso Processing failed.");
      const data = await response.json();
      setTorsoResult(data);
      alert("Torso processing completed successfully!");
    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred during Torso processing. Please try again.");
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

      <div style={{ display: "flex", gap: "10px", marginBottom: "15px" }}>
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
            transition: "background 0.3s ease",
            boxShadow: "0px 4px 8px rgba(0, 123, 255, 0.3)"
          }}
        >
          {loading ? "Processing..." : "Process Weekly"}
        </button>
        <button 
          onClick={handleProcessNemaBody} 
          disabled={loading}
          style={{
            padding: "12px 24px",
            fontSize: "16px",
            color: "white",
            backgroundColor: loading ? "#999" : "#6f42c1",
            border: "none",
            borderRadius: "8px",
            cursor: loading ? "not-allowed" : "pointer",
            transition: "background 0.3s ease",
            boxShadow: "0px 4px 8px rgba(111, 66, 193, 0.3)"
          }}
        >
          {loading ? "Processing..." : "Process Nema Body"}
        </button>
        <button 
          onClick={handleProcessTorso} 
          disabled={loading}
          style={{
            padding: "12px 24px",
            fontSize: "16px",
            color: "white",
            backgroundColor: loading ? "#999" : "#28a745",
            border: "none",
            borderRadius: "8px",
            cursor: loading ? "not-allowed" : "pointer",
            transition: "background 0.3s ease",
            boxShadow: "0px 4px 8px rgba(40, 167, 69, 0.3)"
          }}
        >
          {loading ? "Processing..." : "Process Torso"}
        </button>
      </div>

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

      {nemaResult && Object.keys(nemaResult).length > 0 && (
        <div style={{
          width: "90%",
          backgroundColor: "white",
          padding: "20px",
          borderRadius: "8px",
          boxShadow: "0px 4px 8px rgba(0, 0, 0, 0.1)",
          marginBottom: "15px",
          textAlign: "center",
        }}>
          <h2 style={{ textAlign: "center", color: "#333", fontSize: "22px", marginBottom: "10px" }}>NEMA Body Results</h2>
          {Object.keys(nemaResult).map((group, idx) => (
            <div key={idx}>
              <h3 style={{ textAlign: "center", color: "#555" }}>{group}</h3>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px", marginBottom: "15px" }}>
                <thead>
                  <tr style={{ backgroundColor: "#6f42c1", color: "white", textAlign: "center" }}>
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
                  {nemaResult[group].map((row, index) => {
                    const orientationType = `${row.Orientation} ${row.Type}`;
                    return (
                      <tr key={index} style={{ textAlign: "center", borderBottom: "1px solid #ddd" }}>
                        <td style={{ padding: "10px" }}>{orientationType}</td>
                        <td style={{ padding: "10px" }}>{parseFloat(row.Mean).toFixed(2)}</td>
                        <td style={{ padding: "10px" }}>{parseFloat(row.Min).toFixed(2)}</td>
                        <td style={{ padding: "10px" }}>{parseFloat(row.Max).toFixed(2)}</td>
                        <td style={{ padding: "10px" }}>{parseFloat(row.Sum).toFixed(2)}</td>
                        <td style={{ padding: "10px" }}>{parseFloat(row.StDev).toFixed(2)}</td>
                        <td style={{ padding: "10px" }}>{parseFloat(row.SNR).toFixed(2)}</td>
                        <td style={{ padding: "10px" }}>{parseFloat(row.PIU).toFixed(2)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}

      {torsoResult && (
        <div style={{
          width: "90%",
          backgroundColor: "white",
          padding: "20px",
          borderRadius: "8px",
          boxShadow: "0px 4px 8px rgba(0, 0, 0, 0.1)",
          marginBottom: "15px",
          textAlign: "center",
        }}>
          <h2 style={{ textAlign: "center", color: "#333", fontSize: "22px", marginBottom: "10px" }}>Torso Results</h2>
          
          {/* Combined Views Section */}
          {torsoResult.combined_results && torsoResult.combined_results.length > 0 && (
            <div style={{ marginBottom: "20px" }}>
              <h3 style={{ textAlign: "center", color: "#555", marginBottom: "10px" }}>Combined Views</h3>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px", marginBottom: "15px" }}>
                <thead>
                  <tr style={{ backgroundColor: "#28a745", color: "white", textAlign: "center" }}>
                    <th style={{ padding: "10px", border: "1px solid #ddd" }}>Region</th>
                    <th style={{ padding: "10px", border: "1px solid #ddd" }}>Signal Max</th>
                    <th style={{ padding: "10px", border: "1px solid #ddd" }}>Signal Min</th>
                    <th style={{ padding: "10px", border: "1px solid #ddd" }}>SNR</th>
                    <th style={{ padding: "10px", border: "1px solid #ddd" }}>Uniformity</th>
                  </tr>
                </thead>
                <tbody>
                  {torsoResult.combined_results.map((row, index) => (
                    <tr key={index} style={{ textAlign: "center", borderBottom: "1px solid #ddd" }}>
                      <td style={{ padding: "10px" }}>{row.Region}</td>
                      <td style={{ padding: "10px" }}>{parseFloat(row["Signal Max"]).toFixed(2)}</td>
                      <td style={{ padding: "10px" }}>{parseFloat(row["Signal Min"]).toFixed(2)}</td>
                      <td style={{ padding: "10px" }}>{parseFloat(row.SNR).toFixed(2)}</td>
                      <td style={{ padding: "10px" }}>{parseFloat(row.Uniformity).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Individual Elements Section */}
          {torsoResult.element_results && torsoResult.element_results.length > 0 && (
            <div>
              <h3 style={{ textAlign: "center", color: "#555", marginBottom: "10px" }}>Individual Elements</h3>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px", marginBottom: "15px" }}>
                <thead>
                  <tr style={{ backgroundColor: "#28a745", color: "white", textAlign: "center" }}>
                    <th style={{ padding: "10px", border: "1px solid #ddd" }}>Element</th>
                    <th style={{ padding: "10px", border: "1px solid #ddd" }}>Signal Mean</th>
                    <th style={{ padding: "10px", border: "1px solid #ddd" }}>Noise SD</th>
                    <th style={{ padding: "10px", border: "1px solid #ddd" }}>SNR</th>
                  </tr>
                </thead>
                <tbody>
                  {torsoResult.element_results.map((row, index) => (
                    <tr key={index} style={{ textAlign: "center", borderBottom: "1px solid #ddd" }}>
                      <td style={{ padding: "10px" }}>{row.Element}</td>
                      <td style={{ padding: "10px" }}>{parseFloat(row["Signal Mean"]).toFixed(2)}</td>
                      <td style={{ padding: "10px" }}>{parseFloat(row["Noise SD"]).toFixed(2)}</td>
                      <td style={{ padding: "10px" }}>{parseFloat(row.SNR).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Download Button */}
          {torsoResult.excel_url && (
            <div style={{ marginTop: "15px" }}>
              <a href={`${BACKEND_URL}${torsoResult.excel_url}`} download>
                <button style={{ 
                  padding: "10px 16px", 
                  fontSize: "14px", 
                  backgroundColor: "#28a745", 
                  color: "white", 
                  border: "none", 
                  borderRadius: "6px", 
                  cursor: "pointer" 
                }}>
                  📊 Download Torso Results
                </button>
              </a>
            </div>
          )}
        </div>
      )}

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
