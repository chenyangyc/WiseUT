# WiseUT
This repository contains the implementation of **WiseUT**, an intelligent framwork for unit test generation.
For convenience, we also provide a Docker image with all dependencies pre-installed, available on Zenodo: https://zenodo.org/records/17220794.


### 🚀 Quick Start

Running **WiseUT** only takes three steps:

1. Clone the WiseUT repository and extract the example project under test.
2. Download the pre-built Docker image (includes runtime environment and dependencies).
3. Run WiseUT inside the Docker container.

#### **Get the Code & Example Project**

```bash
git clone git@github.com:chenyangyc/WiseUT.git
cd WiseUT/project_under_test

# unpack the sample project under test
tar -xzvf project.tar.gz
cd ../..
```

####  Load the Docker Image

Download our Docker image 【link】, then import it:

```bash
cat wiseut_docker_image.tar.gz.part_* > wiseut_docker_image.tar.gz
gzip -d -c wiseut_docker_image.tar.gz > wiseut_docker_image.tar

docker import wiseut_docker_image.tar wiseut:v1

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

This is the demonstration video for WiseUT.
<iframe width="560" height="315" src="https://www.youtube.com/embed/DmszXs0eEOE?si=91LKTnm9gg4AF8Fg" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

For detailed documentation about the implementation and usage details, please refer to [this](DETAILED_DOCUMENTATION.md).