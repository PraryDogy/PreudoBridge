pip install --upgrade pip setuptools wheel
pip install aggdraw --prefer-binary
docker build -t pseudo_bridge .
docker run --rm pseudo_bridge
docker run -v /path/to/local/data:/app/data my_docker_image