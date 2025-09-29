# WiseUT
This repository contains the implementation of **WiseUT**, An intelligent framwork for unit test generation.
For convenience, we also provide a Docker image with all dependencies pre-installed, available on Zenodo: 【link】.


### 🚀 Quick Start

Running **WiseUT** only takes three steps:

1. Clone the WiseUT repository and extract the example project under test.
2. Download the pre-built Docker image (includes runtime environment and dependencies).
3. Run WiseUT inside the Docker container.

#### **Get the Code & Example Project**

```bash
git clone git@github.com:chenyangyc/WiseUT.git
cd WiseUT

# unpack the sample project under test
cd project_under_test
tar -xzvf project.tar.gz
cd ../..
```

####  Load the Docker Image

Download our Docker image 【link】, then import it:

```bash
unzip wiseut_image.tar.gz
docker import wiseut_image.tar wiseut:v1

docker run --network host --name wiseut \
  -v ./WiseUT:/data/WiseUT \
  -it wiseut:v1 /bin/bash
```

> 💡 Tip: If you need a proxy, configure it in `~/.bashrc` and `/usr/share/maven/conf/settings.xml`.

#### Run WiseUT

Once inside the container, activate the environment and start experimenting:

```bash
conda activate llm_new
cd /data/WiseUT

# generate tests with high coverage
python main.py --config ./main_config.json --module coverage

# perform test refinement
python main.py --config ./main_config.json --module refine

# detect Python type errors
python main.py --config ./main_config.json --module defect
```

**✨ You’re all set! Explore WiseUT and its main functionalities.**

