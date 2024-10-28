pip install --upgrade pip setuptools wheel
pip install aggdraw --prefer-binary
docker build -t pseudo_bridge .
docker run --rm -v /Volumes/Macintosh\ HD:/app pseudo_bridge
