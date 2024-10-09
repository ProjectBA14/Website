// Toggle Ticket Views
document.querySelectorAll('.toggle-btn').forEach(button => {
    button.addEventListener('click', function() {
        let status = this.getAttribute('data-status');
        toggleTickets(status);
    });
});

function toggleTickets(status) {
    let rows = document.querySelectorAll('.ticket-row');
    rows.forEach(row => {
        let ticketStatus = row.getAttribute('data-status').toLowerCase();
        if (status === 'all' || ticketStatus === status) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Sorting logic for Created At column
let sortDirection = true;
document.getElementById('sortDateHeader').addEventListener('click', function() {
    sortTableByDate();
});

function sortTableByDate() {
    const table = document.getElementById('tickets-table');
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.querySelectorAll('tr.ticket-row'));

    const createdAtIndex = Array.from(table.tHead.rows[0].cells).findIndex(cell => cell.textContent.includes('Created At'));
    if (createdAtIndex === -1) return;

    const validRows = rows.filter(row => row.cells[createdAtIndex].textContent.trim());
    validRows.sort((rowA, rowB) => {
        const dateA = parseDateString(rowA.cells[createdAtIndex].textContent.trim());
        const dateB = parseDateString(rowB.cells[createdAtIndex].textContent.trim());
        return sortDirection ? dateA - dateB : dateB - dateA;
    });

    sortDirection = !sortDirection;
    document.getElementById('sortIndicator').textContent = sortDirection ? '↑' : '↓';
    validRows.forEach(row => tbody.appendChild(row));
    fixHistoryRowsAfterSort();
}

function parseDateString(dateString) {
    const [datePart, timePart] = dateString.split(' ');
    const [year, month, day] = datePart.split('-').map(Number);
    const [hours, minutes, seconds] = timePart ? timePart.split(':').map(Number) : [0, 0, 0];
    return new Date(year, month - 1, day, hours, minutes, seconds);
}

function fixHistoryRowsAfterSort() {
    let rows = document.querySelectorAll('.ticket-row');
    rows.forEach(row => {
        let ticketId = row.getAttribute('data-ticket-id');
        let historyRow = document.getElementById('history-' + ticketId);
        if (historyRow) {
            row.parentNode.insertBefore(historyRow, row.nextSibling);
        }
    });
}

// Search and Filter Logic
document.getElementById('searchInput').addEventListener('input', filterTickets);
document.getElementById('productFilter').addEventListener('change', filterTickets);
document.getElementById('priorityFilter').addEventListener('change', filterTickets);

function filterTickets() {
    let searchValue = document.getElementById('searchInput').value.toLowerCase().trim();
    let productFilter = document.getElementById('productFilter').value.toLowerCase();
    let priorityFilter = document.getElementById('priorityFilter').value.toLowerCase();

    let ticketRows = document.querySelectorAll('.ticket-row');
    ticketRows.forEach(row => {
        let text = row.textContent.toLowerCase();
        let product = row.cells[5].textContent.toLowerCase().trim();
        let priority = row.cells[4].textContent.toLowerCase().trim();

        let matchesSearch = text.includes(searchValue);
        let matchesProduct = !productFilter || product === productFilter;
        let matchesPriority = !priorityFilter || priority === priorityFilter;

        if (matchesSearch && matchesProduct && matchesPriority) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Toggle Ticket History
document.querySelectorAll('.view-history-btn').forEach(button => {
    button.addEventListener('click', function() {
        let ticketId = this.getAttribute('data-ticket-id');
        let historyRow = document.getElementById('history-' + ticketId);
        if (historyRow.style.display === 'none' || historyRow.style.display === '') {
            historyRow.style.display = 'table-row';
        } else {
            historyRow.style.display = 'none';
        }
    });
});