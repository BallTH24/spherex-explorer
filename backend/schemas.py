from typing import List, Literal, Tuple
from pydantic import BaseModel, Field


class EpochPoint(BaseModel):
    mjd: float
    ra: float
    dec: float
    flux_ujy: float


class EpochsInfo(BaseModel):
    epoch1: EpochPoint
    epoch2: EpochPoint


class KinematicsInfo(BaseModel):
    separation_arcsec: float
    proper_motion_arcsec_yr: float
    position_angle_deg: float
    flux_change_pct: float


class AiAnalysisInfo(BaseModel):
    is_real_dipole: bool
    dipole_confidence: float = Field(..., ge=0.0, le=1.0)
    predicted_class: str
    estimated_temp_k: float
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    detected_molecules: List[str]


class CatalogSource(BaseModel):
    source: Literal["Gaia DR3", "AllWISE"]
    x: float
    y: float
    ra: float
    dec: float


class CatalogCrossmatchInfo(BaseModel):
    gaia_dr3_match: bool
    allwise_match: bool
    nearby_sources: List[CatalogSource]


class SpectralAbsorptionMarker(BaseModel):
    molecule: str
    range_um: Tuple[float, float]


class SpectrumBandPoint(BaseModel):
    band: int
    wavelength_um: float
    flux_ujy: float
    flux_err: float


class ImageLayers64x64(BaseModel):
    epoch1_asinh: List[List[float]]
    epoch2_asinh: List[List[float]]
    difference_snr: List[List[float]]


class SpherexTargetBundle(BaseModel):
    target_id: str
    title: str
    target_category: Literal["moving_object", "variable_star", "anomaly_candidate"]
    epochs: EpochsInfo
    kinematics: KinematicsInfo
    ai_analysis: AiAnalysisInfo
    catalog_crossmatch: CatalogCrossmatchInfo
    spectral_absorption_markers: List[SpectralAbsorptionMarker]
    spectrum_102_bands: List[SpectrumBandPoint]
    image_layers_64x64: ImageLayers64x64
