function openTab(evt, tabName) {
    var tabcontent = document.getElementsByClassName('tabcontent');
    for (var i = 0; i < tabcontent.length; i++) {
        tabcontent[i].classList.remove('active');
    }
    var tablinks = document.getElementsByClassName('tablinks');
    for (var i = 0; i < tablinks.length; i++) {
        tablinks[i].classList.remove('active');
    }
    document.getElementById(tabName).classList.add('active');
    evt.currentTarget.classList.add('active');
}

const sidebar = document.getElementById('sidebar');
const mainContent = document.getElementById('main-content');
document.body.addEventListener('mousemove', function(event) {
    if (event.clientX < 30) {
        sidebar.style.left = '0';
        mainContent.style.marginLeft = '250px';
    } else if (event.clientX > 280) {
        sidebar.style.left = '-250px';
        mainContent.style.marginLeft = '0';
    }
});

const productSelect = document.getElementById('product');
const issueSelect = document.getElementById('issue');

productSelect.addEventListener('change', (e) => {
    const selectedProduct = e.target.value;
    const issueOptions = {
        'network-connectivity': [
            'Internet is very slow',
            'Weak Signal / Bad Signal',
            'Router Configuration and Troubleshooting',
            'VPN access and Setup Issues',
            'Network Security Vulnerabilities (Firewall and Malware Protection)',
            'Network Cable Connection issue',
            'Other Network / Connectivity Issues'
        ],
        'pc': [
            'Not turning on',
            'Glitching',
            'Slow performance',
            'Other issue'
        ],
        'projector': [
            'Not turning on',
            'Glitching',
            'Slow performance',
            'Other issue'
        ],
        'printer': [
            'Not printing',
            'Paper jam',
            'Ink or toner issue',
            'Other issue'
        ],
        'scanner': [
            'Not scanning',
            'Scan quality issue',
            'Other issue'
        ],
        'laptop': [
            'Laptop is not starting',
            'Laptop is overheating',
            'Laptop is shutting down automatically',
            'Laptop is very slow / lagging',
            'OS not booting (Blue Screen of Death or Black Screen)',
            'Missing or Corrupt Drivers',
            'Display Issue',
            'Issue in installing / uninstalling a program',
            'Storage / Data Issue',
            'Peripheral Device Issue (mouse etc.)',
            'Security and Privacy Issue',
            'Battery Issue',
            'User Account Issue',
            'Backup & Recovery Issue',
            'Other Laptop Issues'
        ],
        'desktop': [
            'Desktop is not starting',
            'Desktop is very slow',
            'Hardware Issues',
            'Desktop is overheating',
            'Desktop is shutting down automatically',
            'OS not booting (Blue Screen of Death or Black Screen)',
            'Missing or Corrupt Drivers',
            'Display Issue',
            'Issue in installing / uninstalling a program',
            'Storage / Data Issue',
            'Peripheral Device Issue (mouse etc.)',
            'Security and Privacy Issue',
            'User Account Issue',
            'Backup & Recovery Issue',
            'Other Desktop Issues'
        ],
        'other': [
            'Other issue'
        ]
    };

    issueSelect.innerHTML = '<option value="">Select an issue</option>';

    if (issueOptions[selectedProduct]) {
        issueOptions[selectedProduct].forEach((issue) => {
            issueSelect.innerHTML += `<option value="${issue.toLowerCase().replace(/\s+/g, '-')}">${issue}</option>`;
        });
    }
});

// Function to render the created tickets in the created tickets list
function renderCreatedTickets() {
    const createdTickets = document.getElementById('created-tickets');
    createdTickets.innerHTML = '';

    // Assuming there's an array named `tickets` containing the tickets data
    if (typeof tickets !== 'undefined' && Array.isArray(tickets)) {
        tickets.forEach((ticket, index) => {
            const createdTicketElement = document.createElement('li');
            createdTicketElement.textContent = `Ticket ${index + 1}: ${ticket.title}`;
            createdTickets.appendChild(createdTicketElement);
        });
    } else {
        console.warn('No tickets array found or it is not an array.');
    }
}
