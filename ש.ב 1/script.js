const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');

// מערך המאחסן את כל היסטוריית השיחה לצורך שמירת הקשר
let chatHistory = [];

function appendMessage(sender, text) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message');
    
    if (sender === 'user') {
        messageDiv.classList.add('user-message');
    } else {
        messageDiv.classList.add('bot-message');
    }
    
    messageDiv.textContent = text;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // הצגת הודעת המשתמש על המסך
    appendMessage('user', text);
    userInput.value = '';

    // הוספת הודעת המשתמש להיסטוריה שנשמרת בזיכרון
    chatHistory.push({ role: "user", content: text });

    try {
        // שליחת כל היסטוריית השיחה לשרת
        const response = await fetch('http://localhost:8000/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: "gpt-4o-mini",
                messages: chatHistory
            })
        });

        if (!response.ok) {
            throw new Error('שגיאה בתקשורת מול השרת');
        }

        const data = await response.json();
        
        // הצגת תשובת הבוט על המסך
        appendMessage('bot', data.output_text);

        // הוספת תשובת הבוט להיסטוריה כדי שייזכור גם אותה בהודעה הבאה
        chatHistory.push({ role: "assistant", content: data.output_text });

    } catch (error) {
        console.error(error);
        appendMessage('bot', 'אופס, אירעה שגיאה בחיבור לשרת.');
    }
}

sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});