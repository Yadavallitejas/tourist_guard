/* Helper to get CSRF token for POST requests (Django default) */
function getCookie(name) {
  const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return v ? v.pop() : '';
}
const csrftoken = getCookie('csrftoken');

// Alert text element
let alertTextElem = null;

function createAlertText() {
  if (!alertTextElem) {
    alertTextElem = document.createElement('div');
    alertTextElem.style.position = 'fixed';
    alertTextElem.style.top = '20px';
    alertTextElem.style.left = '50%';
    alertTextElem.style.transform = 'translateX(-50%)';
    alertTextElem.style.backgroundColor = '#ff4d4d'; // brighter red
    alertTextElem.style.color = 'white';
    alertTextElem.style.padding = '15px 30px';
    alertTextElem.style.borderRadius = '8px';
    alertTextElem.style.zIndex = '10000';
    alertTextElem.style.fontSize = '18px';
    alertTextElem.style.fontWeight = 'bold';
    alertTextElem.style.boxShadow = '0 0 15px rgba(255, 0, 0, 0.7)';
    alertTextElem.style.textAlign = 'center';
    alertTextElem.style.maxWidth = '90%';
    alertTextElem.style.cursor = 'pointer';
    alertTextElem.title = 'Click to dismiss alert';
    alertTextElem.addEventListener('click', () => {
      alertTextElem.style.display = 'none';
    });
    document.body.appendChild(alertTextElem);
  }
}

function showAlertText(message) {
  createAlertText();
  alertTextElem.textContent = message;
  alertTextElem.style.display = 'block';
}

function hideAlertText() {
  if (alertTextElem) {
    alertTextElem.style.display = 'none';
  }
}

// New polling location script sending lat/lon every 30s to /api/location/update/
async function sendLocation() {
  if (!navigator.geolocation) {
    console.log("No GPS available");
    return;
  }

  navigator.geolocation.getCurrentPosition(async (pos) => {
    const fd = new FormData();
    fd.append("lat", pos.coords.latitude);
    fd.append("lon", pos.coords.longitude);

    const resp = await fetch("/api/location/update/", {
      method: "POST",
      body: fd,
      credentials: "include"
    });
    const data = await resp.json();

    if (data.alert) {
      showAlertText("⚠️ " + data.alert);
    } else {
      hideAlertText();
    }
  });
}

// Send every 30s
setInterval(sendLocation, 30000);
