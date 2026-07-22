// SPDX-License-Identifier: LGPL-3.0-or-later
// SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP
// Collaboration

#include "UpstreamTagger.h"

#include <cmath>
#include <iostream>

#include "FairVolume.h"
#include "ShipDetectorList.h"
#include "ShipGeoUtil.h"
#include "ShipStack.h"
#include "TGeoManager.h"
#include "TGeoMedium.h"
#include "TParticle.h"
#include "TString.h"
#include "TVector3.h"
#include "TVirtualMC.h"
#include "UpstreamTaggerPoint.h"
using std::cout;
using std::endl;

UpstreamTagger::UpstreamTagger()
    : Detector("UpstreamTagger", kTRUE, kUpstreamTagger), det_zPos(0) {}

UpstreamTagger::UpstreamTagger(const char* name, Bool_t active)
    : Detector(name, active, kUpstreamTagger), det_zPos(0) {}

Bool_t UpstreamTagger::ProcessHits(FairVolume* vol) {
  /** This method is called from the MC stepping */
  // Set parameters at entrance of volume. Reset ELoss.
  if (gMC->IsTrackEntering()) {
    fELoss = 0.;
    fTime = gMC->TrackTime() * 1.0e09;
    fLength = gMC->TrackLength();
    gMC->TrackPosition(fPos);
    gMC->TrackMomentum(fMom);
  }

  // Sum energy loss for all steps in the active volume
  fELoss += gMC->Edep();

  // Create vetoPoint at exit of active volume
  if (gMC->IsTrackExiting() || gMC->IsTrackStop() ||
      gMC->IsTrackDisappeared()) {
    if (fELoss == 0.) {
      return kFALSE;
    }

    fTrackID = gMC->GetStack()->GetCurrentTrackNumber();
    fEventID = gMC->CurrentEvent();
    Int_t tileId;
    gMC->CurrentVolID(tileId);

    TParticle* p = gMC->GetStack()->GetCurrentTrack();
    Int_t pdgCode = p->GetPdgCode();
    TLorentzVector Pos;
    gMC->TrackPosition(Pos);
    TLorentzVector Mom;
    gMC->TrackMomentum(Mom);
    Double_t xmean = (fPos.X() + Pos.X()) / 2.;
    Double_t ymean = (fPos.Y() + Pos.Y()) / 2.;
    Double_t zmean = (fPos.Z() + Pos.Z()) / 2.;

    AddHit(fEventID, fTrackID, tileId, TVector3(xmean, ymean, zmean),
           TVector3(fMom.Px(), fMom.Py(), fMom.Pz()), fTime, fLength, fELoss,
           pdgCode, TVector3(Pos.X(), Pos.Y(), Pos.Z()),
           TVector3(Mom.Px(), Mom.Py(), Mom.Pz()));

    // Increment number of veto det points in TParticle
    ShipStack* stack = dynamic_cast<ShipStack*>(gMC->GetStack());
    stack->AddPoint(kUpstreamTagger);
  }

  return kTRUE;
}

void UpstreamTagger::ConstructGeometry() {
  TGeoVolume* top = gGeoManager->GetTopVolume();

  ShipGeo::InitMedium("pterphenyl");
  ShipGeo::InitMedium("UBTOpticalGrease");
  ShipGeo::InitMedium("PMTglass");
  ShipGeo::InitMedium("silicon");
  TGeoMedium* scintillator = gGeoManager->GetMedium("pterphenyl");
  TGeoMedium* opticalGrease = gGeoManager->GetMedium("UBTOpticalGrease");
  TGeoMedium* pmtGlass = gGeoManager->GetMedium("PMTglass");
  TGeoMedium* silicon = gGeoManager->GetMedium("silicon");
  if (!scintillator || !opticalGrease || !pmtGlass || !silicon) {
    Fatal("ConstructGeometry", "A UBT tile or PMT medium was not found.");
  }
  if (fTileX <= 0. || fTileY <= 0. || fTileZ <= 0. ||
      fSmallTileZ <= 0. || fLargeTileZ <= 0. || fSizeX < fTileX ||
      fSizeY < fTileY || fPMTX <= 0. || fPMTY <= 0. ||
      fPMTX > fTileX || fPMTY > fTileY || fGreaseZ <= 0. ||
      fWindowZ <= 0. || fPhotocathodeZ <= 0.) {
    Fatal("ConstructGeometry", "Invalid UBT detector or tile dimensions.");
  }

  // fEnvelopeZ records the longitudinal space reserved in the integration
  // layout. The tile and its PMT stack are centred together in that space.
  const Double_t moduleZ = fTileZ + fGreaseZ + fWindowZ + fPhotocathodeZ;
  if (moduleZ > fEnvelopeZ) {
    Fatal("ConstructGeometry",
          "UBT tile and PMT are thicker than their allocated envelope.");
  }

  fDetector = new TGeoVolumeAssembly("Upstream_Tagger");

  if (!fRegions.empty()) {
    Int_t smallRegions = 0;
    Int_t bigRegions = 0;
    for (const Region& region : fRegions) {
      if (region.sizeX <= 0. || region.sizeY <= 0. ||
          (region.constituentTileSize != 2. &&
           region.constituentTileSize != 4.)) {
        Fatal("ConstructGeometry", "Invalid entry in the UBT detector map.");
      }
      const TString volumeName =
          TString::Format("UpstreamTaggerRegion%d_%dcm", region.id,
                          static_cast<Int_t>(region.constituentTileSize));
      const Double_t regionThickness =
          region.constituentTileSize == 2. ? fSmallTileZ : fLargeTileZ;
      TGeoVolume* regionVolume = gGeoManager->MakeBox(
          volumeName, scintillator, region.sizeX / 2., region.sizeY / 2.,
          regionThickness / 2.);
      regionVolume->SetLineColor(region.constituentTileSize == 2. ? kGreen + 2
                                                                  : kBlue);
      AddSensitiveVolume(regionVolume);
      fDetector->AddNode(regionVolume, region.id,
                         new TGeoTranslation(region.x, region.y, 0.));
      smallRegions += region.constituentTileSize == 2.;
      bigRegions += region.constituentTileSize == 4.;
    }
    top->AddNode(fDetector, 1, new TGeoTranslation(0., 0., det_zPos));
    cout << " Z Position (Upstream Tagger) " << det_zPos << ", "
         << fRegions.size() << " mapped regions (" << smallRegions
         << " with 20 x 20 x 5 mm3 tiles, " << bigRegions
         << " with 40 x 40 x 10 mm3 tiles)" << endl;
    return;
  }

  TGeoVolume* tile =
      gGeoManager->MakeBox("UpstreamTaggerTile", scintillator, fTileX / 2.,
                           fTileY / 2., fTileZ / 2.);
  tile->SetLineColor(kGreen + 2);
  AddSensitiveVolume(tile);

  TGeoVolume* grease =
      gGeoManager->MakeBox("UpstreamTaggerOpticalGrease", opticalGrease,
                           fPMTX / 2., fPMTY / 2., fGreaseZ / 2.);
  TGeoVolume* window =
      gGeoManager->MakeBox("UpstreamTaggerPMTWindow", pmtGlass, fPMTX / 2.,
                           fPMTY / 2., fWindowZ / 2.);
  TGeoVolume* photocathode =
      gGeoManager->MakeBox("UpstreamTaggerPhotocathode", silicon, fPMTX / 2.,
                           fPMTY / 2., fPhotocathodeZ / 2.);
  grease->SetLineColor(kYellow);
  window->SetLineColor(kCyan);
  photocathode->SetLineColor(kBlue);

  const Double_t tileZ = -0.5 * (moduleZ - fTileZ);
  const Double_t greaseZ = tileZ + fTileZ / 2. + fGreaseZ / 2.;
  const Double_t windowZ = tileZ + fTileZ / 2. + fGreaseZ + fWindowZ / 2.;
  const Double_t photocathodeZ =
      tileZ + fTileZ / 2. + fGreaseZ + fWindowZ + fPhotocathodeZ / 2.;

  for (Int_t row = 0; row < GetNRows(); ++row) {
    for (Int_t column = 0; column < GetNColumns(); ++column) {
      const Int_t tileId = GetTileID(row, column);
      const Double_t x = GetTileX(column);
      const Double_t y = GetTileY(row);
      fDetector->AddNode(tile, tileId, new TGeoTranslation(x, y, tileZ));
      fDetector->AddNode(grease, tileId, new TGeoTranslation(x, y, greaseZ));
      fDetector->AddNode(window, tileId, new TGeoTranslation(x, y, windowZ));
      fDetector->AddNode(photocathode, tileId,
                         new TGeoTranslation(x, y, photocathodeZ));
    }
  }

  top->AddNode(fDetector, 1, new TGeoTranslation(0., 0., det_zPos));
  cout << " Z Position (Upstream Tagger) " << det_zPos << ", " << GetNRows()
       << " x " << GetNColumns() << " scintillator tiles with PMTs" << endl;
}

Int_t UpstreamTagger::GetNColumns() const {
  return static_cast<Int_t>(std::floor(fSizeX / fTileX + 1.e-9));
}

Int_t UpstreamTagger::GetNRows() const {
  return static_cast<Int_t>(std::floor(fSizeY / fTileY + 1.e-9));
}

Int_t UpstreamTagger::GetTileID(Int_t row, Int_t column) const {
  return row * GetNColumns() + column;
}

Double_t UpstreamTagger::GetTileX(Int_t column) const {
  return (column + 0.5) * fTileX - GetNColumns() * fTileX / 2.;
}

Double_t UpstreamTagger::GetTileY(Int_t row) const {
  return (row + 0.5) * fTileY - GetNRows() * fTileY / 2.;
}
