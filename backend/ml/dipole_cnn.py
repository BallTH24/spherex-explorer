from pathlib import Path
from typing import Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader

from .synthetic_data import generate_synthetic_dipole_samples

WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "models_weights"
CNN_MODEL_PATH = WEIGHTS_DIR / "dipole_cnn.pt"


class DipoleCNN(nn.Module):
    """
    โมเดล 2D-CNN สำหรับจำแนกคู่จุด Dipole (วัตถุเคลื่อนที่)
    ออกจากสัญญาณรบกวน, จุดเดี่ยว (Monopole/Variable Star) และรังสีคอสมิก
    บนภาพ Difference SNR ขนาด 16x16
    """
    def __init__(self):
        super().__init__()
        self.conv_stack = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2),  # -> (16, 8, 8)
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((2, 2)),  # -> (32, 2, 2)
        )
        self.fc_stack = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 2 * 2, 32),
            nn.ReLU(),
            nn.Dropout(0.25),
            nn.Linear(32, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.conv_stack(x)
        logits = self.fc_stack(features)
        return logits


_GLOBAL_CNN: DipoleCNN | None = None


def get_or_train_dipole_cnn() -> DipoleCNN:
    """โหลดโมเดล CNN จากดิสก์ หรือเทรนใหม่บนชุดข้อมูลจำลองอย่างรวดเร็ว (< 2 วินาที)"""
    global _GLOBAL_CNN
    if _GLOBAL_CNN is not None:
        return _GLOBAL_CNN

    model = DipoleCNN()
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    if CNN_MODEL_PATH.exists():
        try:
            model.load_state_dict(torch.load(str(CNN_MODEL_PATH), weights_only=True, map_location="cpu"))
            model.eval()
            _GLOBAL_CNN = model
            return model
        except Exception:
            pass

    # เทรนโมเดลบน Synthetic Dipole Data
    x_train, y_train = generate_synthetic_dipole_samples(n_samples=400)
    dataset = TensorDataset(torch.from_numpy(x_train), torch.from_numpy(y_train))
    loader = DataLoader(dataset, batch_size=32, shuffle=True)

    optimizer = optim.Adam(model.parameters(), lr=0.003, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()

    model.train()
    for _ in range(8):
        for bx, by in loader:
            optimizer.zero_grad()
            out = model(bx)
            loss = criterion(out, by)
            loss.backward()
            optimizer.step()

    model.eval()
    try:
        torch.save(model.state_dict(), str(CNN_MODEL_PATH))
    except Exception:
        pass

    _GLOBAL_CNN = model
    return model


def predict_dipole_confidence(
    model: DipoleCNN,
    cutout_16x16: np.ndarray,
) -> Tuple[bool, float]:
    """
    ส่งภาพ Cutout 16x16 เข้าโมเดล CNN และคืนค่า (is_real_dipole, confidence)
    """
    model.eval()
    with torch.no_grad():
        norm = cutout_16x16.copy()
        ptp = float(np.ptp(norm))
        if ptp > 1e-6:
            norm = (norm - float(np.mean(norm))) / ptp
        tensor = torch.from_numpy(norm).unsqueeze(0).unsqueeze(0).float()
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1).squeeze().numpy()
        confidence = float(probs[1])
        is_real = bool(confidence >= 0.50)
    return is_real, round(confidence, 4)
