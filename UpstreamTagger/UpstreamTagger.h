// SPDX-License-Identifier: LGPL-3.0-or-later
// SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP
// Collaboration

#ifndef UPSTREAMTAGGER_UPSTREAMTAGGER_H_
#define UPSTREAMTAGGER_UPSTREAMTAGGER_H_

#include <map>
#include <vector>

#include "Detector.h"
#include "ShipUnit.h"
#include "TLorentzVector.h"
#include "TVector3.h"

class UpstreamTaggerPoint;
class FairVolume;
class TClonesArray;

using ShipUnit::cm;
using ShipUnit::m;

/**
 * @brief Upstream Background Tagger (UBT) detector
 *
 * The UBT is a segmented scintillator detector placed upstream of the decay
 * volume and used for background tagging.
 *
 * Current Implementation:
 * - An inactive vacuum mother volume with segmented scintillator plates
 * - Mixed granularity:
 *   5 cm x 5 cm plates in the central 6 m x 4 m region and
 *   10 cm x 10 cm plates elsewhere
 * - Default coverage: 10m (X) x 10m (Y) x 16cm (Z)
 * - Z position and box dimensions are set from geometry_config.py
 * - Configured via SetZposition() and SetBoxDimensions()
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
    xbox_fulldet = x;
    ybox_fulldet = y;
    zbox_fulldet = z;
  }

  /**  Create the detector geometry */
  void ConstructGeometry() override;

  /** Detector parameters.*/

  Double_t det_zPos;  //!  z-position of detector (set via SetZposition)
  // Detector box dimensions (set via SetBoxDimensions, defaults provided below)
  Double_t xbox_fulldet = 10.0 * m;  //!  X dimension (default: 10.0 m)
  Double_t ybox_fulldet = 10.0 * m;  //!  Y dimension (default: 10.0 m)
  Double_t zbox_fulldet =
      16.0 * cm;  //!  Z dimension/thickness (default: 16 cm)

 private:
  TGeoVolume* UpstreamTagger_fulldet;  // Timing_detector_1 object
  TGeoVolume* scoringPlaneUBText;      // Sensitive plate volume
  /** container for data points */

  UpstreamTagger(const UpstreamTagger&) = delete;
  UpstreamTagger& operator=(const UpstreamTagger&) = delete;
};

#endif  // UPSTREAMTAGGER_UPSTREAMTAGGER_H_
