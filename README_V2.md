# Erebus - The Versitile Test Harness
Erebus is a powerful, open-source test harness designed to bring flexibility and robustness to your software testing workflow. Named after the primordial deity of darkness in Greek mythology, Erebus sheds light on the hidden corners of your software systems, uncovering performance bottlenecks and functional issues.

## What is Erebus?
At its core, Erebus is an extensible testing framework that empowers developers and QA engineers to conduct comprehensive performance and functional tests on diverse software systems. Whether you're optimising a high-traffic web service or ensuring the reliability of a complex event-driven application, Erebus provides the tools you need.

## Key Features
* 🔧 Extensible Architecture: Tailor Erebus to fit your unique testing requirements.
* 🚀 Performance Testing: Identify bottlenecks and optimise your system's speed.
* ✅ Functional Testing: Ensure every component works as intended.
* 🌐 Multi-Protocol Support: Send test files via HTTP, Kafka, and more.
* 🛠️ Easy Test Setup: Streamlined base functionality for quick test configuration.

Erebus isn't just a tool; it's a test harness that adapts to your needs, ensuring your software not only works but excels under real-world conditions.

## Installation Guide
## Prerequisites
Before installing Erebus, ensure you have the following:
* Python (v3.11 or later)
* Docker (latest stable version)

Python 3.11 introduces performance improvements and new features that Erebus leverages for efficient test execution. Docker is used for containerisation, ensuring consistent environments across different setups.

## Using Docker Compose (Recommended)
We provide a Docker Compose file that sets up Erebus with the correct volumes, ports, and environment variables. This is the easiest and most consistent way to run Erebus:

1. Clone the repo
```sh
git clone https://github.com/xtuml/erebus.git
cd erebus
```