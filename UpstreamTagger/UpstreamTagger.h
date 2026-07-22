// SPDX-License-Identifier: LGPL-3.0-or-later
// SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP
// Collaboration

#ifndef UPSTREAMTAGGER_UPSTREAMTAGGER_H_
#define UPSTREAMTAGGER_UPSTREAMTAGGER_H_

#include <vector>

#include "Detector.h"
#include "ShipUnit.h"
#include "TLorentzVector.h"
#include "TVector3.h"

class UpstreamTaggerPoint;
class FairVolume;
class TClonesArray;

/**
 * @brief Upstream Background Tagger (UBT) detector
 *
 * The active plane uses the coarse regions from the UBT_DIGI simulation map.
 * Each region records whether it represents 20 x 20 or 40 x 40 mm^2
 * p-terphenyl tiles. Optical photon production and transport are deliberately
 * not simulated here: an MC point stores the energy deposited in a mapped
 * region, identified by its copy number.
 */

class UpstreamTagger : public SHiP::Detector<UpstreamTaggerPoint> {
 public:
  /**      Name :  Detector Name
   *       Active: kTRUE for active detectors (ProcessHits() will be called)
   *               kFALSE for inactive detectors
   */
  UpstreamTagger(const char* Name, Bool_t Active);

  /** default constructor */
  UpstreamTagger();

  /**   this method is called for each step during simulation
   *    (see FairMCApplication::Stepping())
   */
  Bool_t ProcessHits(FairVolume* v = nullptr) override;

  /** Sets detector position and sizes */
  void SetZposition(Double_t z) { det_zPos = z; }
  void SetBoxDimensions(Double_t x, Double_t y, Double_t z) {
    fSizeX = x;
    fSizeY = y;
    fEnvelopeZ = z;
  }
  void SetTileDimensions(Double_t x, Double_t y, Double_t z) {
    fTileX = x;
    fTileY = y;
    fTileZ = z;
  }
  void SetMappedTileThicknesses(Double_t smallTileZ, Double_t largeTileZ) {
    fSmallTileZ = smallTileZ;
    fLargeTileZ = largeTileZ;
  }
  void SetPMTDimensions(Double_t x, Double_t y, Double_t greaseZ,
                        Double_t windowZ, Double_t photocathodeZ) {
    fPMTX = x;
    fPMTY = y;
    fGreaseZ = greaseZ;
    fWindowZ = windowZ;
    fPhotocathodeZ = photocathodeZ;
  }

  /** Add one coarse simulation region from the UBT detector map.
   * constituentTileSize is retained in centimetres so that the same detector
   * ID can later select the 2 x 2 or 4 x 4 cm2 digitization response.
   */
  void AddRegion(Int_t id, Double_t x, Double_t y, Double_t sizeX,
                 Double_t sizeY, Double_t constituentTileSize) {
    fRegions.push_back({id, x, y, sizeX, sizeY, constituentTileSize});
  }

  Int_t GetNColumns() const;
  Int_t GetNRows() const;
  Int_t GetTileID(Int_t row, Int_t column) const;
  Double_t GetTileX(Int_t column) const;
  Double_t GetTileY(Int_t row) const;

  /**  Create the detector geometry */
  void ConstructGeometry() override;

  /** Detector parameters.*/

  Double_t det_zPos;  //! z-position of the active tile plane

 private:
  struct Region {
    Int_t id;
    Double_t x;
    Double_t y;
    Double_t sizeX;
    Double_t sizeY;
    Double_t constituentTileSize;
  };

  std::vector<Region> fRegions;  //! coarse regions loaded from detector map
  Double_t fSizeX = 4.4 * ShipUnit::m;        //! detector width
  Double_t fSizeY = 6.4 * ShipUnit::m;        //! detector height
  Double_t fEnvelopeZ = 16.0 * ShipUnit::cm;  //! allocated longitudinal space
  Double_t fTileX = 4.0 * ShipUnit::cm;       //! tile width
  Double_t fTileY = 4.0 * ShipUnit::cm;       //! tile height
  Double_t fTileZ = 1.0 * ShipUnit::cm;       //! fallback tile thickness
  Double_t fSmallTileZ = 0.5 * ShipUnit::cm;  //! 20 x 20 mm2 tile thickness
  Double_t fLargeTileZ = 1.0 * ShipUnit::cm;  //! 40 x 40 mm2 tile thickness
  Double_t fPMTX = 0.6 * ShipUnit::cm;        //! PMT active width
  Double_t fPMTY = 0.6 * ShipUnit::cm;        //! PMT active height
  Double_t fGreaseZ = 0.02 * ShipUnit::cm;    //! optical grease thickness
  Double_t fWindowZ = 0.1 * ShipUnit::cm;     //! PMT window thickness
  Double_t fPhotocathodeZ = 0.01 * ShipUnit::cm;  //! photocathode thickness
  /** container for data points */

  UpstreamTagger(const UpstreamTagger&) = delete;
  UpstreamTagger& operator=(const UpstreamTagger&) = delete;
};

#endif  // UPSTREAMTAGGER_UPSTREAMTAGGER_H_
