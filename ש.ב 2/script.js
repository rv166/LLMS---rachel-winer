const homeworkForm = document.getElementById('homework-form');
const submitButton = document.getElementById('submit-button');
const statusMessage = document.getElementById('status-message');
const results = document.getElementById('results');
const gradeValue = document.getElementById('grade-value');
const feedbackText = document.getElementById('feedback-text');
const recommendationsList = document.getElementById('recommendations-list');

function showError(message) {
    statusMessage.textContent = message;
    statusMessage.hidden = false;
}

function renderResults(data) {
    if (
        !Number.isInteger(data.grade) ||
        data.grade < 0 ||
        data.grade > 100 ||
        typeof data.feedback !== 'string' ||
        !Array.isArray(data.recommendations) ||
        !data.recommendations.every((recommendation) => typeof recommendation === 'string')
    ) {
        throw new Error('התקבלה תשובה בפורמט לא צפוי. נסו שוב בעוד רגע.');
    }

    gradeValue.textContent = data.grade;
    feedbackText.textContent = data.feedback;
    recommendationsList.replaceChildren();

    data.recommendations.forEach((recommendation) => {
        const item = document.createElement('li');
        item.textContent = recommendation;
        recommendationsList.appendChild(item);
    });

    results.hidden = false;
    results.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

homeworkForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!homeworkForm.reportValidity()) return;

    const formData = new FormData(homeworkForm);
    statusMessage.hidden = true;
    results.hidden = true;
    submitButton.disabled = true;
    submitButton.querySelector('.button-label').textContent = 'בודקים את התרגיל...';
    submitButton.querySelector('i').className = 'bi bi-arrow-repeat';

    try {
        const response = await fetch('http://localhost:8000/check-homework', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                teacher_task: formData.get('teacher_task'),
                student_solution: formData.get('student_solution')
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'לא הצלחנו לבדוק את התרגיל. נסו שוב.');
        }

        renderResults(data);
    } catch (error) {
        console.error(error);
        showError(error.message || 'אירעה שגיאה בחיבור לשרת. ודאו שהשרת פועל ונסו שוב.');
    } finally {
        submitButton.disabled = false;
        submitButton.querySelector('.button-label').textContent = 'בדיקת התרגיל';
        submitButton.querySelector('i').className = 'bi bi-arrow-left';
    }
});
