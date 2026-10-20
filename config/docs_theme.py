"""Shared, synchronized documentation theme; stores no credentials."""
from fastapi.responses import HTMLResponse

THEME = """
<style id="mt5-theme">
:root{--page:#f8fafc;--panel:#fff;--text:#172033;--muted:#526176;--line:#cbd5e1;--code:#eef2f7;--link:#1d4ed8;color-scheme:light}
:root[data-theme=dark]{--page:#101827;--panel:#1d293b;--text:#e5edf8;--muted:#b8c5d9;--line:#475569;--code:#243247;--link:#8bc5ff;color-scheme:dark}
html,body{background:var(--page)!important;color:var(--text)!important}
body{font-family:system-ui,sans-serif}
header{border-color:var(--line)!important}header p{color:var(--muted)!important}
a{color:var(--link)}
body>pre,body>p code{background:var(--code)!important;color:var(--text)!important}
input,select,textarea{background:var(--panel)!important;color:var(--text)!important;border:1px solid var(--line)!important;border-radius:5px}
button{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:6px}
nav button{background:var(--panel)!important;color:var(--text)!important}
nav button[aria-pressed=true]{background:#2563eb!important;color:white!important}
iframe{background:var(--page)!important}
#theme-control{display:flex;justify-content:flex-end;align-items:center;gap:8px;padding:10px 20px;font:14px system-ui;color:var(--muted)}
#theme-control select{padding:6px 10px;min-width:100px}
body:has(>header) #theme-control{position:absolute;top:14px;right:24px;padding:0;z-index:10}
body:has(>header)>header{position:relative;padding-right:210px}
@media(max-width:600px){body:has(>header) #theme-control{top:12px;right:16px}body:has(>header)>header{padding-top:58px;padding-right:24px}}
.swagger-ui{color:var(--text)}
.swagger-ui .info .title,.swagger-ui .info p,.swagger-ui .info li,.swagger-ui .info h1,.swagger-ui .info h2,.swagger-ui .info h3,
.swagger-ui .opblock-tag,.swagger-ui .opblock .opblock-summary-description,.swagger-ui .opblock .opblock-summary-path,
.swagger-ui .opblock-description-wrapper p,.swagger-ui .opblock-description-wrapper li,.swagger-ui .opblock-description-wrapper h3,
.swagger-ui .parameter__name,.swagger-ui .parameter__type,.swagger-ui .parameter__in,.swagger-ui .parameter__deprecated,
.swagger-ui .response-col_status,.swagger-ui .response-col_description,.swagger-ui .response-col_links,
.swagger-ui .responses-inner h4,.swagger-ui .responses-inner h5,.swagger-ui table thead tr th,.swagger-ui table tbody tr td,
.swagger-ui .tab li,.swagger-ui label,.swagger-ui .model,.swagger-ui .model-title,.swagger-ui .model-box-control,
.swagger-ui section.models h4,.swagger-ui section.models h4 span,.swagger-ui .prop-type,.swagger-ui .prop-format,
.swagger-ui .dialog-ux .modal-ux,.swagger-ui .dialog-ux .modal-ux-header h3,.swagger-ui .dialog-ux .modal-ux-content h4,
.swagger-ui .opblock .opblock-section-header h4,.swagger-ui .opblock .opblock-section-header label{color:var(--text)!important}
.swagger-ui .info a,.swagger-ui .renderedMarkdown a{color:var(--link)!important}
.swagger-ui .scheme-container,.swagger-ui .opblock .opblock-section-header,.swagger-ui .dialog-ux .modal-ux,
.swagger-ui section.models .model-container,.swagger-ui .model-box,.swagger-ui .responses-wrapper{background:var(--panel)!important}
.swagger-ui .opblock-tag,.swagger-ui section.models,.swagger-ui table thead tr th,.swagger-ui table tbody tr td{border-color:var(--line)!important}
.swagger-ui .renderedMarkdown code{background:var(--code)!important;color:var(--text)!important}
.swagger-ui .renderedMarkdown pre{background:var(--code)!important;color:var(--text)!important;padding:14px;border-radius:6px;overflow:auto}
.swagger-ui .btn{color:var(--text);border-color:var(--line)}
.swagger-ui .btn.authorize{color:#16a36b;border-color:#16a36b}
.swagger-ui .scheme-container{box-sizing:border-box;width:calc(100% - 40px)!important;max-width:1420px;margin:0 auto 24px!important;padding:16px 20px!important;box-shadow:none!important;border:1px solid var(--line);border-radius:8px}
.swagger-ui .scheme-container .schemes{box-sizing:border-box;display:flex;align-items:center;justify-content:space-between;gap:16px;width:100%;margin:0!important;padding:0!important}
.swagger-ui .scheme-container .auth-wrapper{display:flex;align-items:center;justify-content:flex-end;gap:12px;margin:0 0 0 auto!important;padding:0}
.swagger-ui .scheme-container .btn.authorize{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:42px;padding:10px 18px;margin:0;line-height:20px}
.swagger-ui .scheme-container .btn.authorize span{padding:0;margin:0}
.swagger-ui .scheme-container .btn.authorize svg{width:18px;height:18px;margin:0}
.swagger-ui .dialog-ux .modal-ux-header{padding:20px 24px;border-bottom:1px solid var(--line)}
.swagger-ui .dialog-ux .modal-ux-content{padding:24px}
.swagger-ui .dialog-ux .auth-container{padding:20px 0;border-color:var(--line)}
.swagger-ui .dialog-ux .auth-container:first-child{padding-top:0}
.swagger-ui .dialog-ux .auth-container h4{margin:0 0 16px}
.swagger-ui .dialog-ux .auth-container .wrapper{padding:0;margin:12px 0}
.swagger-ui .dialog-ux .auth-container input{box-sizing:border-box;max-width:100%;padding:10px 12px;min-height:42px}
.swagger-ui .dialog-ux .auth-btn-wrapper{display:flex;justify-content:center;flex-wrap:wrap;gap:12px;padding:20px 0 0}
.swagger-ui .dialog-ux .auth-btn-wrapper .btn{margin:0;padding:10px 18px;min-height:42px}
@media(max-width:600px){.swagger-ui .scheme-container{padding:14px 16px!important}.swagger-ui .scheme-container .schemes{flex-wrap:wrap;padding:0!important}.swagger-ui .dialog-ux .modal-ux-content{padding:18px}.swagger-ui .dialog-ux .modal-ux-header{padding:16px 18px}}
.swagger-ui .btn.execute{background:#2563eb;color:#fff}
:root[data-theme=dark] .swagger-ui svg:not(.authorization__btn svg){fill:#b8c5d9}
</style>
<script>
(()=>{
 const media=window.matchMedia('(prefers-color-scheme: dark)');
 let preference='system';
 try{preference=localStorage.getItem('mt5-docs-theme')||'system';}catch(e){}
 function apply(value){
  preference=['light','dark','system'].includes(value)?value:'system';
  document.documentElement.dataset.theme=preference==='system'?(media.matches?'dark':'light'):preference;
  const select=document.getElementById('theme-select');if(select)select.value=preference;
 }
 apply(preference);
 window.addEventListener('storage',e=>{if(e.key==='mt5-docs-theme')apply(e.newValue||'system');});
 media.addEventListener('change',()=>{if(preference==='system')apply('system');});
 document.addEventListener('DOMContentLoaded',()=>{
  // Embedded REST and WebSocket pages follow the single portal picker.
  if(window.self!==window.top)return;
  const control=document.createElement('div');control.id='theme-control';
  control.innerHTML='<label for="theme-select">Theme</label><select id="theme-select" aria-label="Documentation theme"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select>';
  document.body.prepend(control);apply(preference);
  document.getElementById('theme-select').onchange=e=>{apply(e.target.value);try{localStorage.setItem('mt5-docs-theme',preference);}catch(e){}};
 });
})();
</script>
"""


def themed(response):
    html = response.body.decode("utf-8").replace("</head>", THEME + "</head>", 1)
    return HTMLResponse(html, status_code=response.status_code, headers={
        key: value for key, value in response.headers.items() if key.lower() not in ("content-length", "content-type")
    })
