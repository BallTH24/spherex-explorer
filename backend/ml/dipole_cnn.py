from pathlib import Path
from typing import Tuple, Any, Dict, Optional
import numpy as np

from .synthetic_data import generate_synthetic_dipole_samples

WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "models_weights"
CNN_MODEL_PATH = WEIGHTS_DIR / "dipole_cnn.npz"


class DipoleCNN:
    """
    โมเดล Neural Network (Pure NumPy Inference Engine) สำหรับจำแนกคู่จุด Dipole (วัตถุเคลื่อนที่)
    ออกจากสัญญาณรบกวน, จุดเดี่ยว (Monopole/Variable Star) และรังสีคอสมิก
    บนภาพ Difference SNR ขนาด 16x16
    ออกแบบมาให้ทำงานด้วย NumPy ล้วน เพื่อให้ Deploy บน Vercel Serverless Function ได้ไม่เกิน 250 MB
    """
    def __init__(self, weights: Optional[Dict[str, np.ndarray]] = None):
        self.weights = weights or {}

    def eval(self) -> "DipoleCNN":
        """Compat method with PyTorch module interface"""
        return self

    def train(self, mode: bool = True) -> "DipoleCNN":
        return self

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Forward pass in pure NumPy.
        Input x: shape (16, 16), (1, 16, 16), (B, 1, 16, 16), or (B, 256)
        Output: logits of shape (B, 2)
        """
        arr = np.asarray(x, dtype=np.float32)
        if arr.ndim == 2 and arr.shape == (16, 16):
            flat = arr.reshape(1, 256)
        elif arr.ndim == 3 and arr.shape[-2:] == (16, 16):
            flat = arr.reshape(-1, 256)
        elif arr.ndim == 4 and arr.shape[-2:] == (16, 16):
            flat = arr.reshape(arr.shape[0], 256)
        elif arr.ndim == 2 and arr.shape[1] == 256:
            flat = arr
        else:
            flat = arr.reshape(1, -1)

        # Normalize features like training data
        ptp = np.ptp(flat, axis=-1, keepdims=True)
        ptp = np.where(ptp > 1e-6, ptp, 1.0)
        norm = (flat - np.mean(flat, axis=-1, keepdims=True)) / ptp

        W0 = self.weights.get("W0")
        b0 = self.weights.get("b0")
        W1 = self.weights.get("W1")
        b1 = self.weights.get("b1")
        W2 = self.weights.get("W2")
        b2 = self.weights.get("b2")

        if W0 is None or W1 is None or W2 is None:
            # Fallback heuristic if weights not loaded
            return np.zeros((flat.shape[0], 2), dtype=np.float32)

        h1 = np.maximum(0.0, norm @ W0 + b0)
        h2 = np.maximum(0.0, h1 @ W1 + b1)
        z = h2 @ W2 + b2  # (B, 1) or (B, 2)

        if z.ndim == 2 and z.shape[1] == 1:
            logits = np.column_stack([-z / 2.0, z / 2.0])
        elif z.ndim == 1:
            z_col = z.reshape(-1, 1)
            logits = np.column_stack([-z_col / 2.0, z_col / 2.0])
        else:
            logits = z
        return logits.astype(np.float32)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return self.forward(x)


_GLOBAL_CNN: Optional[DipoleCNN] = None


def get_or_train_dipole_cnn(force_retrain: bool = False) -> DipoleCNN:
    """โหลดโมเดล CNN/MLP จากไฟล์ .npz หรือเทรนใหม่บนชุดข้อมูลจำลองอย่างรวดเร็ว (< 1 วินาที)"""
    global _GLOBAL_CNN
    if _GLOBAL_CNN is not None and not force_retrain:
        return _GLOBAL_CNN

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    if CNN_MODEL_PATH.exists() and not force_retrain:
        try:
            with np.load(str(CNN_MODEL_PATH)) as data:
                weights = {k: data[k] for k in data.files}
                model = DipoleCNN(weights=weights)
                _GLOBAL_CNN = model
                return model
        except Exception:
            pass

    # เทรนโมเดลบน Synthetic Dipole Data ด้วย scikit-learn MLPClassifier
    from sklearn.neural_network import MLPClassifier

    x_train, y_train = generate_synthetic_dipole_samples(n_samples=600, rng_seed=42)
    x_flat = np.array([
        ((s - np.mean(s)) / (np.ptp(s) if np.ptp(s) > 1e-6 else 1.0)).flatten()
        for s in x_train
    ], dtype=np.float32)

    clf = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        max_iter=300,
        random_state=42,
    )
    clf.fit(x_flat, y_train)

    weights = {
        "W0": clf.coefs_[0].astype(np.float32),
        "b0": clf.intercepts_[0].astype(np.float32),
        "W1": clf.coefs_[1].astype(np.float32),
        "b1": clf.intercepts_[1].astype(np.float32),
        "W2": clf.coefs_[2].astype(np.float32),
        "b2": clf.intercepts_[2].astype(np.float32),
    }

    try:
        np.savez_compressed(str(CNN_MODEL_PATH), **weights)
    except Exception:
        pass

    model = DipoleCNN(weights=weights)
    _GLOBAL_CNN = model
    return model


def predict_dipole_confidence(
    arg1: Any,
    arg2: Any = None,
    signature_info: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, float]:
    """
    ส่งภาพ Cutout 16x16 เข้าโมเดล DipoleCNN และคืนค่า (is_real_dipole, confidence)
    รันด้วย Pure NumPy Inference
    รองรับทั้ง:
    - predict_dipole_confidence(model, cutout_16x16)
    - predict_dipole_confidence(cutout_16x16, signature_info=...)
    """
    if isinstance(arg1, DipoleCNN):
        model = arg1
        cutout_16x16 = arg2
    else:
        model = get_or_train_dipole_cnn()
        cutout_16x16 = arg1
        if isinstance(arg2, dict) and signature_info is None:
            signature_info = arg2

    model.eval()
    arr = np.asarray(cutout_16x16, dtype=np.float32)
    logits = model(arr)
    # Softmax on axis -1
    exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
    probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
    probs_flat = probs.reshape(-1, 2)
    confidence = float(probs_flat[0, 1])
    is_real = bool(confidence >= 0.50)

    if signature_info:
        if signature_info.get("is_monopole_pattern", False) and not signature_info.get("is_dipole_pattern", False):
            is_real = False
            confidence = float(min(0.20, confidence))
        elif signature_info.get("is_dipole_pattern", False):
            is_real = True
            confidence = float(max(0.85, confidence))

    return is_real, round(confidence, 4)
