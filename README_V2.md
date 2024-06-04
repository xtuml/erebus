<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/github_username/repo_name">
    <img src="docs/images/logo.png" alt="Logo" width="80" height="80" style="border-radius: 10px;">
    </a>

<h3 align="center">Erebus</h3>

  <p align="center">
    Erebus is a powerful, open-source test harness designed to bring flexibility and robustness to your software testing workflow. Named after the primordial deity of darkness in Greek mythology, Erebus sheds light on the hidden corners of your software systems, uncovering performance bottlenecks and functional issues.
    <br />
    <!-- <a href="https://github.com/github_username/repo_name"><strong>Explore the docs »</strong></a> -->
    <!-- <br /> -->
    <br />
    <a href="https://github.com/github_username/repo_name">View Demo</a>
    ·
    <a href="https://github.com/github_username/repo_name/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/github_username/repo_name/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <ul>
        <li><a href="#what-is-erebus">What is Erebus?</a></li>
        <li><a href="#key-features">Key Features</a></li>
      </ul>
    </li>
    <li><a href="#quickstart">Quickstart</a></li>
    <li>
      <a href="#installation-guide">Installation Guide</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#using-docker-compose-recommended">Using Docker Compose (Recommended)</a></li>
        <li><a href="#manual-installation-for-development">Manual Installation (For Development)</a></li>
      </ul>
    </li>
    <li><a href="#deployment">Deployment</a></li>
  </ol>
</details>

## What is Erebus?
At its core, Erebus is an extensible testing framework that empowers developers and QA engineers to conduct comprehensive performance and functional tests on diverse software systems. Whether you're optimising a high-traffic web service or ensuring the reliability of a complex event-driven application, Erebus provides the tools you need.

## Key Features
* 🔧 Extensible Architecture: Tailor Erebus to fit your unique testing requirements.
* 🚀 Performance Testing: Identify bottlenecks and optimise your system's speed.
* ✅ Functional Testing: Ensure every component works as intended.
* 🌐 Multi-Protocol Support: Send test files via HTTP, Kafka, and more.
* 🛠️ Easy Test Setup: Streamlined base functionality for quick test configuration.

Erebus isn't just a tool; it's a test harness that adapts to your needs, ensuring your software not only works but excels under real-world conditions.

# Quickstart
1. Clone the repo
```sh
git clone https://github.com/xtuml/erebus.git
cd erebus
```
2. Run with docker compose
```sh
docker compose up --build
```

This assumes you have docker installed on your machine (https://www.docker.com/products/docker-desktop/)

# Installation Guide

## Prerequisites
Before installing Erebus, ensure you have the following:
* Python (v3.11 or later)
* Docker (latest stable version)

Python 3.11 introduces performance improvements and new features that Erebus leverages for efficient test execution. Docker is used for containerisation, ensuring consistent environments across different setups.

## Using Docker Compose (Recommended)
We provide a Docker Compose file that sets up Erebus with the correct volumes, ports, and environment variables. This is the easiest and most consistent way to run Erebus:

1. Clone the repo:
```sh
git clone https://github.com/xtuml/erebus.git
cd erebus
```
2. (Optional) Customise settings:
* Configure Erebus by copying the `./test_harness/config/default_config.config` file to `./config/config.config`
```sh
cp ./test_harness/config/default_config.config ./config/config.config # MacOS, Linux

copy .\test_harness\config\default_config.config .\config\config.config # Windows
```
* Override settings by copying the setting under `[non-default]`. Eg.
```sh
[DEFAULT]
requests_max_retries = 5
requests_timeout = 10

[non-default]
requests_max_retries = 10 # This will override the default setting
```
3. Build and run using Docker Compose:
```sh
docker compose up --build
```

## Manual Installation (For Development)
If you're contributing to Erebus or need a custom setup:
```sh
# Clone and navigate
git clone https://github.com/yourusername/erebus.git
cd erebus

# Run install script for test-event-generator (Janus)
# https://github.com/xtuml/janus
./scripts/install_repositories.sh

# Create and activate a virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install dependencies (make sure requirements.txt exists)
pip install -r requirements.txt
```

## Deployment
It is recommended to deploy the test harness in the same VPC (or private network) as the machine containing the system to be tested to avoid exposure to the public internet. 

![](./docs/diagrams/deployment/deployment.png)