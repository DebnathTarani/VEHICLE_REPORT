function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('addCityBtn').addEventListener('click', () => {
    const cityName = prompt("Enter city name:");
    if (!cityName) return;

    const section = document.createElement('div');
    section.className = 'city-section';
    section.innerHTML = `<strong>City: ${escapeHtml(cityName)}</strong><br><em>Section added successfully.</em>`;
    document.getElementById('citySections').appendChild(section);
  });
});

