@echo off
REM ============================================================
REM InkPi 书法评测系统 - Windows CPU 版本训练脚本
REM 适用于: Windows 10/11 (无 GPU 或 GPU 不可用)
REM ============================================================

setlocal enabledelayedexpansion

REM ============================================================
REM 配置参数 (CPU 优化)
REM ============================================================
if not defined SAMPLES_PER_LEVEL set SAMPLES_PER_LEVEL=100
if not defined EPOCHS set EPOCHS=30
if not defined BATCH_SIZE set BATCH_SIZE=16
if not defined LEARNING_RATE set LEARNING_RATE=1e-3
if not defined DATA_SOURCE set DATA_SOURCE=synthetic
if not defined NUM_WORKERS set NUM_WORKERS=0

REM 获取脚本目录和项目根目录
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

REM 全局变量
set TOTAL_COUNT=0

echo.
echo ============================================================
echo   InkPi 书法评测系统 - Windows CPU 版本训练
echo ============================================================
echo.
echo 项目根目录: %PROJECT_ROOT%
echo 配置参数:
echo   - 每级别样本数: %SAMPLES_PER_LEVEL%
echo   - 训练轮数: %EPOCHS%
echo   - 批大小: %BATCH_SIZE%
echo   - 学习率: %LEARNING_RATE%
echo   - 数据源: %DATA_SOURCE%
echo   - 数据加载线程: %NUM_WORKERS%
echo.
echo [!] CPU 训练速度较慢，建议:
echo   - 使用合成数据集 (DATA_SOURCE=synthetic)
echo   - 样本数量较少 (SAMPLES_PER_LEVEL=100)
echo   - 训练轮数较少 (EPOCHS=30)
echo.

REM ============================================================
REM 步骤 1: 环境检查
REM ============================================================
echo [1/7] 环境检查...

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装 Python
    echo 请从 https://www.python.org/downloads/ 下载并安装 Python 3.8+
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION%

REM 检查 pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未安装 pip
    exit /b 1
)

echo [OK] pip 已安装

echo.

REM ============================================================
REM 步骤 2: 安装依赖
REM ============================================================
echo [2/7] 安装 Python 依赖...

cd /d "%PROJECT_ROOT%"

REM 创建虚拟环境（如果不存在）
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        echo 请确保已安装 python -m venv
        exit /b 1
    )
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 升级 pip
python -m pip install --upgrade pip

REM 安装 PyTorch (CPU 版本，体积更小)
echo 安装 PyTorch (CPU 版本)...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

REM 安装其他依赖
echo 安装其他依赖...
pip install numpy opencv-python scipy pillow tqdm onnx onnxruntime onnxscript

REM 验证 PyTorch
python -c "import torch; print(f'PyTorch 版本: {torch.__version__}'); print(f'CUDA 可用: {torch.cuda.is_available()}'); print(f'CPU 核心数: {torch.get_num_threads()}')"

echo.

REM ============================================================
REM 步骤 3: 准备数据集
REM ============================================================
cd /d "%PROJECT_ROOT%"

if "%DATA_SOURCE%"=="real" (
    echo [3/7] 下载真实书法数据集...
    
    REM 检查是否已有真实数据
    set REAL_COUNT=0
    for /f %%i in ('dir /b /s data\real\*.png 2^>nul ^| find /c /v ""') do set REAL_COUNT=%%i
    
    if !REAL_COUNT! geq 100 (
        echo [OK] 已存在 !REAL_COUNT! 张真实数据，跳过下载
    ) else (
        echo 从 GitHub 下载真实书法数据集...
        python training\download_real_dataset.py --source github
    )
    
    set DATA_DIR=%PROJECT_ROOT%\data\real
) else (
    echo [3/7] 生成合成数据集...
    
    REM 检查是否已有足够数据
    set EXISTING_SAMPLES=0
    for /f %%i in ('dir /b /s data\synthetic\good\*.png 2^>nul ^| find /c /v ""') do set EXISTING_SAMPLES=%%i
    
    if !EXISTING_SAMPLES! geq %SAMPLES_PER_LEVEL% (
        echo [OK] 已存在 !EXISTING_SAMPLES! 个样本，跳过数据集生成
    ) else (
        echo 生成 %SAMPLES_PER_LEVEL% 个样本 per 级别...
        python training\dataset_builder.py --samples %SAMPLES_PER_LEVEL% --output "%PROJECT_ROOT%\data\synthetic" --quality good medium poor
    )
    
    set DATA_DIR=%PROJECT_ROOT%\data\synthetic
)

REM 统计总样本数
set TOTAL_COUNT=0
for /f %%i in ('dir /b /s "%DATA_DIR%\*.png" 2^>nul ^| find /c /v ""') do set TOTAL_COUNT=%%i

echo [OK] 数据集统计: 总计 !TOTAL_COUNT! 张

if !TOTAL_COUNT! lss 10 (
    echo [错误] 样本数量过少 (至少需要 10 张)
    exit /b 1
)

echo.

REM ============================================================
REM 步骤 4: 开始训练
REM ============================================================
echo [4/7] 开始训练模型...

cd /d "%PROJECT_ROOT%"

echo [!] 预计训练时间: 2-4 小时 (取决于 CPU 性能)
echo.

REM 运行训练 (CPU 优化: 禁用 AMP + 小 batch + 少线程)
python training\train_siamese.py ^
    --data "%DATA_DIR%" ^
    --epochs %EPOCHS% ^
    --batch-size %BATCH_SIZE% ^
    --lr %LEARNING_RATE% ^
    --device cpu ^
    --workers %NUM_WORKERS%

if errorlevel 1 (
    echo [错误] 训练过程出错
    exit /b 1
)

echo [OK] 训练完成!
echo.

REM ============================================================
REM 步骤 5: 验证模型
REM ============================================================
echo [5/7] 验证训练结果...

cd /d "%PROJECT_ROOT%"

REM 检查模型文件
if not exist "models\siamese_calligraphy_best.pth" (
    echo [错误] 训练后的模型文件不存在
    exit /b 1
)

echo [OK] PyTorch 模型生成成功

echo.

REM ============================================================
REM 步骤 6: 导出 ONNX
REM ============================================================
echo [6/7] 验证 ONNX 模型...

cd /d "%PROJECT_ROOT%"

REM 验证 ONNX 模型
if exist "models\siamese_calligraphy.onnx" (
    echo [OK] ONNX 模型已导出: models\siamese_calligraphy.onnx
    
    REM 显示模型信息
    python -c "import onnx; model = onnx.load('models/siamese_calligraphy.onnx'); print('ONNX 模型信息:'); print(f'  - IR 版本: {model.ir_version}'); print(f'  - 生产者: {model.producer_name}'); print('  - 输入:'); [print(f'      {inp.name}: {[d.dim_value for d in inp.type.tensor_type.shape.dim]}') for inp in model.graph.input]; print('  - 输出:'); [print(f'      {out.name}: {[d.dim_value for d in out.type.tensor_type.shape.dim]}') for out in model.graph.output]"
) else (
    echo [警告] ONNX 模型未找到，请检查训练日志
)

echo.

REM ============================================================
REM 步骤 7: 结果汇总
REM ============================================================
echo [7/7] 结果汇总

cd /d "%PROJECT_ROOT%"

echo.
echo ============================================================
echo   训练完成!
echo ============================================================
echo.
echo 输出文件:
echo.

REM 模型文件
if exist "models\siamese_calligraphy_best.pth" (
    echo   [OK] models\siamese_calligraphy_best.pth
)

if exist "models\siamese_calligraphy_final.pth" (
    echo   [OK] models\siamese_calligraphy_final.pth
)

if exist "models\siamese_calligraphy.onnx" (
    echo   [OK] models\siamese_calligraphy.onnx
)

if exist "models\training_history.json" (
    echo   [OK] models\training_history.json
)

echo.
echo 训练统计:
echo   - 数据集大小: %TOTAL_COUNT% 张
echo   - 训练轮数: %EPOCHS%
echo   - 批大小: %BATCH_SIZE%
echo.

REM 部署说明
echo 部署说明:
echo.
echo 1. 复制 ONNX 模型到树莓派:
echo    使用 WinSCP 或 scp 命令:
echo    scp models\siamese_calligraphy.onnx pi@raspberrypi:~/.inkpi/data/models/
echo.
echo 2. 或复制到项目数据目录:
echo    copy models\siamese_calligraphy.onnx %%USERPROFILE%%\.inkpi\data\models\
echo.
echo 3. 验证模型:
echo    python -c "import onnxruntime as ort; sess = ort.InferenceSession('models/siamese_calligraphy.onnx'); print('模型加载成功')"
echo.
echo ============================================================
echo.
echo [提示] CPU 版本训练速度较慢，后续可升级到 GPU 训练以加速
echo.

REM 退出虚拟环境
deactivate

endlocal
