        // Google Sheets integration
        function showSheetsInfo(sheetsData) {
            if (!sheetsData || !sheetsData.url) return;
            
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-success alert-dismissible fade show mt-3';
            alertDiv.innerHTML = `
                <h6 class="alert-heading"><i class="bi bi-table"></i> Сохранено в Google Sheets!</h6>
                <p class="mb-2">Транскрибация успешно сохранена в Google Таблицу</p>
                <hr>
                <div class="d-flex gap-2">
                    <a href="${sheetsData.url}" target="_blank" class="btn btn-sm btn-success">
                        <i class="bi bi-box-arrow-up-right"></i> Открыть таблицу
                    </a>
                    <button class="btn btn-sm btn-outline-success" onclick="copyToClipboard('${sheetsData.spreadsheet_id}')">
                        <i class="bi bi-clipboard"></i> Копировать ID
                    </button>
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            
            const container = document.getElementById('result-container');
            container.insertBefore(alertDiv, container.firstChild);
        }
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                // Visual feedback
                const btn = event.target.closest('button');
                const originalHTML = btn.innerHTML;
                btn.innerHTML = '<i class="bi bi-check"></i> Скопировано';
                setTimeout(() => btn.innerHTML = originalHTML, 2000);
            });
        }

