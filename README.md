# Intelligent Computer Vision System for Automated Monitoring and Behavioral Analysis of Milkfish (*Chanos chanos*)

## 1. Project Overview

The **Intelligent Computer Vision System for Automated Monitoring and Behavioral Analysis of Milkfish (*Chanos chanos*)** is a web-based application designed to assist in monitoring and analyzing milkfish fingerlings through computer vision and artificial intelligence.

The system processes recorded video footage to detect and track milkfish, analyze their movement, and identify observable behavioral patterns. It aims to support more efficient fish monitoring and provide useful information for fisheries and aquaculture applications.

## 2. Objectives

The system aims to:

- Detect and count milkfish in recorded video footage.
- Track individual detected fish across video frames.
- Analyze fish movement using extracted tracking information.
- Classify observable behavioral patterns.
- Identify unusual movement patterns for further observation.
- Present monitoring results through a web-based dashboard.

## 3. Main Features

| Feature | Description |
|---|---|
| Fish Detection | Detects milkfish using a trained YOLO model. |
| Fish Counting | Displays the number of detected milkfish. |
| Object Tracking | Tracks detected fish using DeepSORT. |
| Movement Analysis | Extracts movement information from tracked fish. |
| Behavioral Classification | Analyzes normal swimming, schooling, and feeding activity. |
| Unusual Movement Monitoring | Identifies movement patterns that may require further observation. |
| Dashboard | Presents detection, tracking, and behavioral analysis results. |
| Video Upload | Allows users to upload recorded videos for processing. |

## 4. Technologies Used

- **Python** – Main programming language
- **Streamlit** – Web-based dashboard
- **YOLOv8** – Milkfish detection
- **DeepSORT** – Object tracking
- **OpenCV** – Video processing and image enhancement
- **CLAHE** – Contrast enhancement
- **NumPy** – Numerical operations
- **Pandas** – Data processing

## 5. System Workflow

1. Upload recorded milkfish video.
2. Process video frames using OpenCV.
3. Enhance image contrast using CLAHE.
4. Detect milkfish using the trained YOLO model.
5. Track detected milkfish using DeepSORT.
6. Extract movement information.
7. Analyze and classify observable behavioral patterns.
8. Display monitoring results in the dashboard.

## 6. Project Structure

```text
MilkfishCVSystem/
│
├── models/
│   └── best.pt
│
├── src/
│   ├── __init__.py
│   ├── alerts.py
│   ├── behavior.py
│   ├── behavior_ui.py
│   ├── combined.py
│   ├── components.py
│   ├── config.py
│   ├── dashboard.py
│   ├── db.py
│   ├── detector.py
│   ├── history.py
│   ├── pipeline.py
│   ├── preprocessing.py
│   ├── storage.py
│   ├── styles.py
│   └── tracker.py
│
├── .streamlit/
│   └── config.toml
│
├── requirements.txt
├── run.py
├── README.md
└── .gitignore
```

## 7. Installation and Setup

### Prerequisites

- Python 3.10 or a compatible version
- pip
- Git
- Trained YOLO model (`best.pt`)

### Step 1: Clone the Repository

```bash
git clone https://github.com/yumi-spec/Intelligence-Computer-Vision-System-for-Automated-Monitoring-and-Behavioral-Analysis.git
```

### Step 2: Navigate to the Project Folder

```bash
cd Intelligence-Computer-Vision-System-for-Automated-Monitoring-and-Behavioral-Analysis
```

### Step 3: Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Run the Application

```bash
streamlit run src/dashboard.py
```

Open the local URL displayed in your terminal to access the dashboard.

## 8. Deployment

The application is designed for deployment through **Streamlit Community Cloud**.

Deployment configuration:

- Repository: GitHub repository
- Branch: `main`
- Main file path: `src/dashboard.py`

Once successfully deployed, the application can be accessed through its Streamlit web address using a computer or mobile phone browser.

## 9. Scope and Limitations

- The current application analyzes uploaded or recorded video footage.
- The system depends on the availability of its trained YOLO model.
- Detection and behavioral classification depend on video quality, visibility, and tracking performance.
- The system's behavioral classifications are intended as monitoring indicators and should not be treated as definitive biological diagnoses.
- Continuous live camera streaming is not currently included.

## 10. Project Status

**Development Stage:** Prototype / Research Project

This project is being developed as an academic capstone project focused on computer vision, automated milkfish monitoring, and behavioral analysis.

## 11. License

This repository is intended for academic and research purposes. Permission should be obtained from the project owners before redistribution or commercial use.
