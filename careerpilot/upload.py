"""Session-bound resume upload for distributed ASGI hosting.

Vercel may route normal HTTP uploads to a different worker than the active
Streamlit WebSocket. Transfer bounded file bytes through the existing component
state channel so they arrive at the session that will parse them.
"""
import base64
from dataclasses import dataclass
import streamlit as st

MAX_BYTES = 3 * 1024 * 1024


@dataclass
class ResumeUpload:
    name: str
    data: bytes

    def getvalue(self):
        return self.data


def decode_upload(value):
    if not isinstance(value, dict):
        return None
    name, encoded = value.get("name"), value.get("data")
    if not isinstance(name, str) or not name.lower().endswith((".pdf", ".docx")):
        raise ValueError("Choose a PDF or DOCX resume.")
    if not isinstance(encoded, str) or len(encoded) > 4 * MAX_BYTES // 3 + 8:
        raise ValueError("Hosted resumes must be smaller than 3 MB.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError("Could not decode the uploaded file. Please select it again.") from exc
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Upload a nonempty resume smaller than 3 MB.")
    return ResumeUpload(name, data)


def session_resume_uploader():
    widget = st.components.v2.component(
        "careerpilot_session_resume_upload",
        html='''<label for="resume-file">Upload PDF or DOCX</label>
        <div class="upload-box"><input id="resume-file" type="file" accept=".pdf,.docx" />
        <button id="clear-file" type="button">Clear</button>
        <p id="file-state" aria-live="polite">Maximum 3 MB. Processed in this session.</p></div>''',
        css='''label{display:block;margin-bottom:8px;font:14px sans-serif}.upload-box{border:1px dashed #a6b6cf;border-radius:10px;padding:18px;background:#f6f8fc}input,button,p{font:14px sans-serif}button{border:1px solid #cad5e5;border-radius:6px;padding:7px 12px;background:white;cursor:pointer}p{color:#52647d;margin-bottom:0}''',
        js='''export default function({parentElement,setStateValue,data}) {
          const input=parentElement.querySelector('input');
          const status=parentElement.querySelector('#file-state');
          if(data && data.name) status.textContent=data.name + ' · ready to read';
          input.onchange=async () => {
            const file=input.files[0];
            if(!file) return;
            if(file.size>3145728 || !/\\.(pdf|docx)$/i.test(file.name)) {
              status.textContent='Choose a PDF or DOCX smaller than 3 MB.';
              setStateValue('file',null); return;
            }
            status.textContent='Loading your document…';
            const reader=new FileReader();
            reader.onerror=()=>{status.textContent='Could not read this file.';setStateValue('file',null);};
            reader.onload=()=>setStateValue('file',{name:file.name,data:String(reader.result).split(',')[1]});
            reader.readAsDataURL(file);
          };
          parentElement.querySelector('#clear-file').onclick=()=>{input.value='';status.textContent='No file selected.';setStateValue('file',null);};
          return ()=>{input.onchange=null;};
        }''',
    )
    current = st.session_state.get("resume_socket_upload", {})
    current_file = current.get("file") if isinstance(current, dict) else None
    result = widget(key="resume_socket_upload", data={"name": current_file.get("name") if isinstance(current_file, dict) else None},
                    default={"file":None}, on_file_change=lambda: None)
    try:
        return decode_upload(result.get("file"))
    except ValueError as exc:
        st.error(str(exc))
        return None
