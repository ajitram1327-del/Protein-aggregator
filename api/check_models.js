import dotenv from 'dotenv';
dotenv.config();

fetch('https://api.groq.com/openai/v1/models', {
    headers: { Authorization: `Bearer ${process.env.GROQ_API_KEY}` }
})
.then(res => res.json())
.then(data => {
    if (data.data) {
        console.log("Available Groq Models for this API Key:");
        console.log(data.data.map(m => m.id).join("\n"));
    } else {
        console.error("Error fetching models:", data);
    }
})
.catch(err => console.error("Fetch error:", err));
