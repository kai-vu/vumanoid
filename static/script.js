function get_state() {
  fetch('/state').then((response) => response.text())
    .then((text) => {
      el = document.getElementById('state')
      html = text.split("\n").map((s) => 
        s?`<div class="${s[0] == '<'? 'q' : 'a'}">${s.slice(1)}</div>`:''
      ).join('\n');
      el.innerHTML = html;
      box = el.parentElement.parentElement;
      box.scrollTop = box.scrollHeight;
  })
  setTimeout(function() {
      get_state();
  }, 1000); // 1 second
}
get_state();



// ! Functions that deal with button events
function post_json(url, body) {
  return fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  })
}

function camera_setting(name, eventtype, prop, callback=(()=>{})) {
  document.getElementById(name).addEventListener(eventtype, function (event) {
    post_json('/camera_set', {[name]: event.currentTarget[prop] })
    callback(event);
    return false;
  });
}
camera_setting("cam_preview",  "change", "checked")
camera_setting("cam_flip",     "change", "checked")
camera_setting("cam_detect",   "change", "checked")
camera_setting("cam_exposure", "change", "value")
camera_setting("cam_contrast", "change", "value")
camera_setting("cam_reset",    "click", "value")

function setSecret() {
  secret = document.getElementById("secret").value;
  post_json('/secret_set', { secret:secret })
  return false;
}

function makeEvent() {
  t = (document.getElementById("eventType").value == "In")? "<" : ">";
  message = t + document.getElementById("event").value;
  document.getElementById("event").value = "";
  fetch('/state', {
    method: 'POST',
    body: message
  })
  return false;
}