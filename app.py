import os
import uuid
import urllib.request

import boto3
from flask import Flask, request, redirect, render_template_string
from werkzeug.utils import secure_filename

BUCKET = os.environ["BUCKET"]
REGION = os.environ["AWS_REGION"]
ALLOWED = {"png", "jpg", "jpeg", "gif", "webp"}

s3 = boto3.client("s3", region_name=REGION)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB


def get_instance_id():
    """Read the instance ID from IMDSv2 so the footer shows which server answered."""
    try:
        tok_req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
        )
        token = urllib.request.urlopen(tok_req, timeout=2).read().decode()
        id_req = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/instance-id",
            headers={"X-aws-ec2-metadata-token": token},
        )
        return urllib.request.urlopen(id_req, timeout=2).read().decode()
    except Exception:
        return "unknown"


IID = get_instance_id()

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f5f4ef">
  <title>PhotoVault | Your photo library</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #202b27;
      --muted: #6c7771;
      --paper: #f5f4ef;
      --surface: #fffefa;
      --line: #e3e6de;
      --green: #315f4d;
      --green-dark: #244638;
      --lime: #d9ed8b;
      --coral: #c45c46;
    }
    * { box-sizing: border-box; }
    body {
      min-height: 100vh;
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: "Avenir Next", Avenir, "Segoe UI", sans-serif;
    }
    .page { width: min(1120px, calc(100% - 48px)); margin: 0 auto; }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 76px;
      border-bottom: 1px solid var(--line);
    }
    .brand { display: flex; align-items: center; gap: 11px; font-weight: 750; letter-spacing: .2px; }
    .brand-mark {
      display: grid;
      width: 34px;
      aspect-ratio: 1;
      place-items: center;
      border-radius: 9px;
      background: var(--green);
      color: var(--lime);
      font-family: Georgia, serif;
      font-size: 21px;
    }
    .library-label { color: var(--muted); font-size: 13px; }
    main { padding: 62px 0 48px; }
    .intro { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 34px; }
    .eyebrow { margin: 0 0 12px; color: var(--green); font-size: 11px; font-weight: 750; letter-spacing: 1.5px; text-transform: uppercase; }
    h1 { margin: 0; font-family: Georgia, "Times New Roman", serif; font-size: 56px; font-weight: 500; letter-spacing: 0; line-height: 1; }
    .subtitle { margin: 13px 0 0; color: var(--muted); font-size: 15px; }
    .photo-count { flex: 0 0 auto; padding: 9px 13px; border: 1px solid var(--line); border-radius: 99px; color: var(--muted); font-size: 12px; }
    .upload-panel {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 20px 22px;
      border: 1px solid #dce4d8;
      border-radius: 8px;
      background: #edf1e9;
    }
    .upload-copy strong { display: block; margin-bottom: 4px; font-size: 14px; }
    .upload-copy span { color: var(--muted); font-size: 12px; }
    .upload-controls { display: flex; align-items: center; gap: 10px; }
    input[type="file"] { max-width: min(320px, 45vw); color: var(--muted); font: inherit; font-size: 12px; }
    input[type="file"]::file-selector-button {
      margin-right: 10px;
      padding: 10px 12px;
      border: 1px solid #cbd6ca;
      border-radius: 6px;
      background: var(--surface);
      color: var(--ink);
      font: inherit;
      cursor: pointer;
    }
    button { font: inherit; cursor: pointer; }
    .upload-button {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 11px 16px;
      border: 0;
      border-radius: 6px;
      background: var(--green);
      color: white;
      font-size: 13px;
      font-weight: 700;
      transition: background .18s ease, transform .18s ease;
    }
    .upload-button:hover { transform: translateY(-1px); background: var(--green-dark); }
    .upload-button svg { width: 15px; height: 15px; }
    .section-heading { display: flex; align-items: baseline; gap: 10px; margin: 42px 0 17px; }
    .section-heading h2 { margin: 0; font-family: Georgia, "Times New Roman", serif; font-size: 24px; font-weight: 500; }
    .section-heading span { color: var(--muted); font-size: 12px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 17px; }
    .photo-card {
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface);
      animation: rise .45s both;
    }
    .photo-card:nth-child(2) { animation-delay: .04s; }
    .photo-card:nth-child(3) { animation-delay: .08s; }
    .photo-card:nth-child(4) { animation-delay: .12s; }
    .photo-frame { overflow: hidden; aspect-ratio: 4 / 3; background: #e5e8df; }
    .photo-frame img { display: block; width: 100%; height: 100%; object-fit: cover; transition: transform .35s ease; }
    .photo-card:hover .photo-frame img { transform: scale(1.035); }
    .photo-actions { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 11px 12px; }
    .photo-name { overflow: hidden; color: var(--muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
    .delete-button { padding: 5px 8px; border: 0; border-radius: 5px; background: transparent; color: var(--coral); font-size: 11px; font-weight: 700; }
    .delete-button:hover { background: #f9ece8; }
    .empty-state { padding: 48px 20px; border: 1px dashed #cbd4c8; border-radius: 8px; text-align: center; }
    .empty-mark { display: grid; width: 42px; height: 42px; margin: 0 auto 13px; place-items: center; border-radius: 50%; background: var(--lime); color: var(--green-dark); }
    .empty-state h3 { margin: 0; font-family: Georgia, "Times New Roman", serif; font-size: 21px; font-weight: 500; }
    .empty-state p { margin: 7px 0 0; color: var(--muted); font-size: 13px; }
    footer { display: flex; justify-content: space-between; gap: 12px; margin-top: 60px; padding: 16px 0; border-top: 1px solid var(--line); color: var(--muted); font-size: 11px; }
    footer b { color: var(--ink); font-weight: 650; }
    :focus-visible { outline: 3px solid #84a85a; outline-offset: 3px; }
    @keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    @media (max-width: 640px) {
      .page { width: min(100% - 32px, 540px); }
      main { padding-top: 42px; }
      .intro { align-items: start; }
      .photo-count { margin-top: 4px; }
      .upload-panel { align-items: stretch; flex-direction: column; gap: 15px; padding: 17px; }
      .upload-controls { align-items: stretch; flex-direction: column; }
      input[type="file"] { max-width: 100%; }
      .upload-button { justify-content: center; }
      .grid { grid-template-columns: repeat(auto-fill, minmax(155px, 1fr)); gap: 11px; }
      .photo-actions { padding: 9px; }
      footer { flex-direction: column; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; transition-duration: .01ms !important; }
    }
  </style>
</head>
<body>
  <div class="page">
    <header class="topbar">
      <div class="brand"><span class="brand-mark" aria-hidden="true">P</span> PhotoVault</div>
      <span class="library-label">Your photo library</span>
    </header>
    <main>
      <section class="intro" aria-labelledby="page-title">
        <div>
          <p class="eyebrow">A little corner of the internet</p>
          <h1 id="page-title">Keep the good<br>moments close.</h1>
          <p class="subtitle">A home for the photos you want to come back to.</p>
        </div>
        <span class="photo-count">{{ keys|length }} photos</span>
      </section>
      <form class="upload-panel" action="/upload" method="post" enctype="multipart/form-data">
        <div class="upload-copy">
          <strong>Add a photo to your collection</strong>
          <span>PNG, JPG, GIF or WebP - up to 5 MB</span>
        </div>
        <div class="upload-controls">
          <input type="file" name="photo" accept="image/*" required aria-label="Choose a photo">
          <button class="upload-button" type="submit">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 16V4m0 0L7 9m5-5 5 5M5 15v4a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Upload photo
          </button>
        </div>
      </form>
      <section aria-labelledby="collection-title">
        <div class="section-heading">
          <h2 id="collection-title">The collection</h2>
          <span>Newest first</span>
        </div>
        {% if keys %}
        <div class="grid">
        {% for k in keys %}
          <article class="photo-card">
            <div class="photo-frame"><img src="/{{ k }}" alt="{{ k.rsplit('/', 1)[-1] }}" loading="lazy"></div>
            <div class="photo-actions">
              <span class="photo-name" title="{{ k.rsplit('/', 1)[-1] }}">{{ k.rsplit('/', 1)[-1] }}</span>
              <form action="/delete" method="post">
                <input type="hidden" name="key" value="{{ k }}">
                <button class="delete-button" type="submit" aria-label="Delete {{ k.rsplit('/', 1)[-1] }}">Delete</button>
              </form>
            </div>
          </article>
        {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
          <span class="empty-mark" aria-hidden="true">*</span>
            h1 { font-size: 40px; }
          <h3>Your collection starts here</h3>
          <p>Choose a photo above and it will show up here.</p>
        </div>
        {% endif %}
      </section>
    </main>
    <footer><span>PhotoVault</span><span>Served by instance <b>{{ iid }}</b></span></footer>
  </div>
</body>
</html>
"""


@app.get("/")
def index():
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix="photos/")
    objs = sorted(resp.get("Contents", []), key=lambda o: o["LastModified"], reverse=True)
    return render_template_string(PAGE, keys=[o["Key"] for o in objs], iid=IID)


@app.post("/upload")
def upload():
    f = request.files.get("photo")
    if f and f.filename:
        name = secure_filename(f.filename)
        if name.rsplit(".", 1)[-1].lower() in ALLOWED:
            key = f"photos/{uuid.uuid4().hex[:8]}-{name}"
            s3.upload_fileobj(f, BUCKET, key, ExtraArgs={"ContentType": f.mimetype})
    return redirect("/")


@app.post("/delete")
def delete():
    key = request.form.get("key", "")
    if key.startswith("photos/"):
        s3.delete_object(Bucket=BUCKET, Key=key)
    return redirect("/")


@app.get("/health")
def health():
    return "ok", 200
