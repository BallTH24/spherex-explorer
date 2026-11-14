export interface EpochPoint {
  mjd: number;
  ra: number;
  dec: number;
  flux_ujy: number;
}

export interface KinematicsInfo {
  separation_arcsec: number;
  proper_motion_arcsec_yr: number;
  position_angle_deg: number;
  flux_change_pct: number;
}

export interface AiAnalysisInfo {
  is_real_dipole: boolean;
  dipole_confidence: number;
  predicted_class: string;
  estimated_temp_k: number;
  anomaly_score: number;
  detected_molecules: string[];
}

export interface CatalogSource {
  source: "Gaia DR3" | "AllWISE";
  x: number;
  y: number;
  ra: number;
  dec: number;
}

export interface CatalogCrossmatchInfo {
  gaia_dr3_match: boolean;
  allwise_match: boolean;
  nearby_sources: CatalogSource[];
}

export interface SpectralAbsorptionMarker {
  molecule: string;
  range_um: [number, number];
}

export interface SpectrumBandPoint {
  band: number;
  wavelength_um: number;
  flux_ujy: number;
  flux_err: number;
}

export interface ImageLayers64x64 {
  epoch1_asinh: number[][];
  epoch2_asinh: number[][];
  difference_snr: number[][];
}

export interface SpherexTargetBundle {
  target_id: string;
  title: string;
  target_category: "moving_object" | "variable_star" | "anomaly_candidate";
  epochs: {
    epoch1: EpochPoint;
    epoch2: EpochPoint;
  };
  kinematics: KinematicsInfo;
  ai_analysis: AiAnalysisInfo;
  catalog_crossmatch: CatalogCrossmatchInfo;
  spectral_absorption_markers: SpectralAbsorptionMarker[];
  spectrum_102_bands: SpectrumBandPoint[];
  image_layers_64x64: ImageLayers64x64;
}
