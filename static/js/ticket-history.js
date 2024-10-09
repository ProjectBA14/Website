// Sorting logic for Created At column
let sortDirection = true; // true = ascending, false = descending
document.getElementById('sortDateHeader').addEventListener('click', function() {
    sortTableByDate();
});

function sortTableByDate() {
    const table = document.getElementById('tickets-table');
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.querySelectorAll('tr.ticket-row'));  // Select only ticket rows, not history rows

    // Find the correct index for the "Created At" column
    const createdAtIndex = Array.from(table.tHead.rows[0].cells).findIndex(cell => cell.textContent.includes('Created At'));

    if (createdAtIndex === -1) {
        console.error("Couldn't find the 'Created At' column.");
        return;
    }

    // Filter out rows with missing or empty "Created At" values
    const validRows = rows.filter(row => {
        const cell = row.cells[createdAtIndex];
        return cell && cell.textContent.trim();  // Only keep rows where the "Created At" column is not empty
    });

    if (validRows.length === 0) {
        console.warn("No rows with valid dates to sort.");
        return;
    }

    // Sort the rows based on the date in the "Created At" column
    validRows.sort((rowA, rowB) => {
        const dateA = parseDateString(rowA.cells[createdAtIndex].textContent.trim());
        const dateB = parseDateString(rowB.cells[createdAtIndex].textContent.trim());

        return sortDirection ? dateA - dateB : dateB - dateA;
    });

    // Toggle sort direction
    sortDirection = !sortDirection;

    // Update the sorting indicator
    document.getElementById('sortIndicator').textContent = sortDirection ? '↑' : '↓';

    // Append sorted rows back to the tbody
    validRows.forEach(row => {
        tbody.appendChild(row);  // Move ticket rows only
    });

    fixHistoryRowsAfterSort();  // Fix the placement of history rows after sorting
}

// Helper function to parse the date string (YYYY-MM-DD HH:MM:SS)
function parseDateString(dateString) {
    const [datePart, timePart] = dateString.split(' ');
    const [year, month, day] = datePart.split('-').map(Number);
    const [hours, minutes, seconds] = timePart ? timePart.split(':').map(Number) : [0, 0, 0];
    
    return new Date(year, month - 1, day, hours, minutes, seconds);
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
