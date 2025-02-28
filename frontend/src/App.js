import React, { useState } from "react";

const BACKEND_URL = "https://automation-backend-qd96qvdda-aviral-bals-projects.vercel.app "; // Change this after deployment

function App() {
    const [message, setMessage] = useState("");

    const fetchMessage = async () => {
        const response = await fetch(`${BACKEND_URL}/`);
        const data = await response.json();
        setMessage(data.message);
    };

    return (
        <div style={{ textAlign: "center", padding: "50px" }}>
            <h1>Welcome to My Full-Stack App</h1>
            <button onClick={fetchMessage}>Get Backend Message</button>
            <p>{message}</p>
        </div>
    );
}

export default App;
