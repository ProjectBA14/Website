// Toggle between Normal and Scheduled Tickets
document.querySelectorAll('.ticket-type-btn').forEach(button => {
    button.addEventListener('click', function() {
        let type = this.getAttribute('data-ticket-type');
        document.getElementById('normal-tickets-section').style.display = (type === 'normal') ? 'block' : 'none';
        document.getElementById('scheduled-tickets-section').style.display = (type === 'scheduled') ? 'block' : 'none';
    });
});

// Sorting logic for Created At column for Normal Tickets
let sortDirection = true; // true = ascending, false = descending
document.getElementById('sortDateHeader').addEventListener('click', function() {
    sortTableByDate('tickets-table', 'Created At', sortDirection);
    sortDirection = !sortDirection;
});

// Sorting logic for Scheduled Tickets
let sortScheduledDirection = true;
document.getElementById('sortScheduledDateHeader').addEventListener('click', function() {
    sortTableByDate('scheduled-tickets-table', 'Created At', sortScheduledDirection);
    sortScheduledDirection = !sortScheduledDirection;
});

function sortTableByDate(tableId, columnTitle, ascending) {
    const table = document.getElementById(tableId);
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const dateIndex = Array.from(table.tHead.rows[0].cells).findIndex(cell => cell.textContent.includes(columnTitle));

    rows.sort((rowA, rowB) => {
        const dateA = new Date(rowA.cells[dateIndex].textContent.trim());
        const dateB = new Date(rowB.cells[dateIndex].textContent.trim());
        return ascending ? dateA - dateB : dateB - dateA;
    });

    rows.forEach(row => tbody.appendChild(row));
}

// Ensure "View History" rows remain correctly placed after sorting
function fixHistoryRowsAfterSort() {
    let rows = document.querySelectorAll('.ticket-row');
    rows.forEach(row => {
        let ticketId = row.getAttribute('data-ticket-id');
        let historyRow = document.getElementById('history-' + ticketId);

        if (historyRow) {
            row.parentNode.insertBefore(historyRow, row.nextSibling); // Ensure the history row is placed after the ticket row
        }
    });
}

// Handle Confirm Resolved Ticket
document.querySelectorAll('.confirm-resolved-btn').forEach(button => {
    button.addEventListener('click', function() {
        let ticketId = this.getAttribute('data-ticket-id');
        let response = this.getAttribute('data-response');

        fetch(`/confirm_resolved_ticket/${ticketId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ response: response })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert("Ticket status updated successfully.");
                window.location.reload();  // Refresh the page to show updated status
            } else {
                alert("Error updating ticket status.");
            }
        })
        .catch(error => {
            console.error("Error:", error);
        });
    });
});

// Handle showing profile modal when clicking on "Assigned to" or "User Email"
document.querySelectorAll('.profile-link').forEach(link => {
    link.addEventListener('click', function(event) {
        event.preventDefault();
        const email = this.getAttribute('data-email');
        
        fetch(`/get_profile_info?email=${encodeURIComponent(email)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('modal-profile-name').textContent = data.profile.name;
                document.getElementById('modal-profile-email').textContent = data.profile.email;
                document.getElementById('modal-profile-phone').textContent = data.profile.phone;
                document.getElementById('modal-profile-role').textContent = data.profile.role;

                document.getElementById('profileModal').style.display = 'block';
            } else {
                alert("Failed to fetch profile information.");
            }
        })
        .catch(error => console.error('Error fetching profile:', error));
    });
});

// Close modal when 'x' is clicked
document.querySelector('.close-btn').addEventListener('click', function() {
    document.getElementById('profileModal').style.display = 'none';
});

// Close modal when clicking outside of it
window.onclick = function(event) {
    if (event.target == document.getElementById('profileModal')) {
        document.getElementById('profileModal').style.display = 'none';
    }
};

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
        let product = row.cells[6].textContent.toLowerCase().trim();
        let priority = row.cells[5].textContent.toLowerCase().trim();

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
document.querySelectorAll('.expand-btn').forEach(button => {
    button.addEventListener('click', function() {
        let ticketId = this.getAttribute('data-ticket-id');
        let historyRow = document.getElementById('history-' + ticketId);

        if (!historyRow) {
            console.error("History row not found for ticket ID:", ticketId);
            return;
        }

        if (historyRow.style.display === 'none' || historyRow.style.display === '') {
            historyRow.style.display = 'table-row'; // Show the history
        } else {
            historyRow.style.display = 'none'; // Hide the history
        }
    });
});
