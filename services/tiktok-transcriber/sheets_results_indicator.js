
// Google Sheets integration for results
function addGoogleSheetsIndicator() {
    // Add indicator after successful transcription
    const resultContainer = document.getElementById('result-container');
    if (!resultContainer) return;
    
    // Check if indicator already exists
    if (document.getElementById('sheets-save-indicator')) return;
    
    const indicator = document.createElement('div');
    indicator.id = 'sheets-save-indicator';
    indicator.className = 'alert alert-success mt-3';
    indicator.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <i class="bi bi-check-circle-fill text-success"></i>
                <strong>Сохранено в Google Sheets!</strong>
                <p class="mb-0 mt-1 small">Данные автоматически добавлены в таблицу истории</p>
            </div>
            <a href="https://docs.google.com/spreadsheets/d/1x5Srd28dGdKlpn_NO3cIN_nzh3mV2ItU5D3ErzhvqYU" 
               target="_blank" 
               class="btn btn-sm btn-success">
                <i class="bi bi-box-arrow-up-right"></i> Открыть таблицу
            </a>
        </div>
    `;
    
    // Insert after results
    const transcriptionCard = document.querySelector('.card-body');
    if (transcriptionCard) {
        transcriptionCard.parentNode.insertBefore(indicator, transcriptionCard.nextSibling);
    }
}

// Modify the original displayResults function to include Google Sheets indicator
const originalDisplayResults = window.displayResults;
if (originalDisplayResults) {
    window.displayResults = function(data) {
        originalDisplayResults(data);
        // Add Google Sheets indicator after displaying results
        setTimeout(addGoogleSheetsIndicator, 500);
    };
}

