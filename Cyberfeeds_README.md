# 🛡️ CyberFeed

Dashboard agregator berita cybersecurity secara real-time, dibangun dengan Streamlit. Mengumpulkan artikel dari 18 sumber keamanan terpercaya dan menampilkannya dalam antarmuka yang bersih dengan fitur filter, pencarian, dan tema visual.

> Built by a SOC Analyst, for the security community.

---

## ✨ Fitur

- **18 sumber feed** — The Hacker News, BleepingComputer, Krebs on Security, SANS ISC, Unit 42, Google Project Zero, NIST NVD, dan lainnya
- **Live ticker** — headline terbaru berjalan otomatis di bagian atas
- **Filter kategori** — Threats, Vulnerabilities, Breaches, CVE, Analysis
- **Filter per sumber** — pilih satu atau beberapa sumber sekaligus
- **Pencarian real-time** — cari berdasarkan judul atau ringkasan artikel
- **Badge NEW** — menandai artikel yang terbit dalam 4 jam terakhir
- **5 tema visual** — Midnight, Obsidian, Terminal, Crimson, Arctic
- **Cache 5 menit** — feed di-refresh otomatis setiap 5 menit
- **Pagination** — navigasi halaman untuk ratusan artikel

---

## 📡 Sumber Feed

| Sumber | Kategori |
|---|---|
| The Hacker News | Threats |
| BleepingComputer | Breaches |
| Krebs on Security | Breaches |
| Dark Reading | Threats |
| SecurityWeek | Threats |
| SANS ISC | Vulnerabilities |
| Schneier on Security | Analysis |
| Unit 42 (Palo Alto) | Analysis |
| Google Project Zero | Vulnerabilities |
| Malwarebytes Labs | Threats |
| WeLiveSecurity (ESET) | Analysis |
| NIST NVD | CVE |
| Exploit-DB | CVE |
| Troy Hunt | Breaches |
| Graham Cluley | Breaches |
| Recorded Future | Analysis |
| Threatpost | Threats |
| HackerOne Hacktivity | CVE |

---

## 🚀 Cara Menjalankan

### 1. Clone repo

```bash
git clone https://github.com/p3nr0s3/Cyberfeeds.git
cd Cyberfeeds
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Jalankan aplikasi

```bash
streamlit run app.py
```

Buka browser di `http://localhost:8501`

---

## 📦 Dependencies

```
streamlit>=1.32.0
feedparser>=6.0.11
requests>=2.31.0
```

---

## 🗂️ Struktur File

```
Cyberfeeds/
├── app.py            # Aplikasi utama Streamlit
├── requirements.txt  # Python dependencies
└── README.md         # Dokumentasi ini
```

---

## ☁️ Deploy ke Streamlit Cloud

1. Fork repo ini
2. Buka [share.streamlit.io](https://share.streamlit.io)
3. Pilih repo → branch `main` → file `app.py`
4. Klik **Deploy** — selesai

---

## 📸 Tampilan

| Tema | Warna Utama |
|---|---|
| Midnight (default) | Biru `#00C2FF` |
| Obsidian | Ungu `#A078FF` |
| Terminal | Hijau `#00FF41` |
| Crimson | Merah `#FF3C50` |
| Arctic | Biru terang (light mode) |

---

## 👤 Author

**Eka Revadiaz** — SOC Analyst

- 🌐 [Portfolio](https://ekarevadiaz.github.io)
- 💼 [LinkedIn](https://www.linkedin.com/in/eka-revadiaz-118920335/)
- 🐙 [GitHub](https://github.com/p3nr0s3)
