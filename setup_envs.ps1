Write-Host "Creating .venv..."
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install ipykernel
.\.venv\Scripts\python -m ipykernel install --user --name=venv --display-name="Python (.venv)"

Write-Host "Creating .venv_tf..."
python -m venv .venv_tf
.\.venv_tf\Scripts\python -m pip install --upgrade pip
.\.venv_tf\Scripts\python -m pip install -r requirements_tf.txt
.\.venv_tf\Scripts\python -m pip install ipykernel
.\.venv_tf\Scripts\python -m ipykernel install --user --name=venv_tf --display-name="Python (.venv_tf)"

Write-Host "Creating .venv_gpu..."
python -m venv .venv_gpu
.\.venv_gpu\Scripts\python -m pip install --upgrade pip
.\.venv_gpu\Scripts\python -m pip install -r requirements_gpu.txt
.\.venv_gpu\Scripts\python -m pip install ipykernel
.\.venv_gpu\Scripts\python -m ipykernel install --user --name=venv_gpu --display-name="Python (.venv_gpu)"

Write-Host "All environments created successfully!"
