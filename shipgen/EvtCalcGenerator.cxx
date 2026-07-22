// SPDX-License-Identifier: LGPL-3.0-or-later
// SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP
// Collaboration

#include "EvtCalcGenerator.h"

#include <string>

#include "FairLogger.h"
#include "FairPrimaryGenerator.h"
#include "TFile.h"
#include "TMath.h"

// -----   Default constructor   -------------------------------------------
EvtCalcGenerator::EvtCalcGenerator() = default;
// -------------------------------------------------------------------------
// -----   Default constructor   -------------------------------------------
Bool_t EvtCalcGenerator::Init(const char* fileName) {
  return Init(fileName, 0);
}
// -----   Default constructor   -------------------------------------------
Bool_t EvtCalcGenerator::Init(const char* fileName, const int startEvent) {
  if (startEvent < 0) {
    LOG(error) << "EvtCalcGenerator: startEvent must be >= 0, got "
               << startEvent;
    return kFALSE;
  }
  fTree.reset();
  fInputFile.reset();
  fDaughterPx = nullptr;
  fDaughterPy = nullptr;
  fDaughterPz = nullptr;
  fDaughterE = nullptr;
  fDaughterMass = nullptr;
  fDaughterPdg = nullptr;
  fInputFile = std::unique_ptr<TFile>(TFile::Open(fileName, "read"));
  LOGF(info, "Info EvtCalcGenerator: Opening input file %s", fileName);
  if (!fInputFile || fInputFile->IsZombie()) {
    LOG(error) << "EvtCalcGenerator: error opening input file " << fileName;
    fInputFile.reset();
    return kFALSE;
  }

  auto* inputTree = dynamic_cast<TTree*>(fInputFile->Get("Events"));
  fTree = std::unique_ptr<TTree>(inputTree);
  if (!fTree) {
    LOG(error) << "EvtCalcGenerator: cannot find convert.C tree Events in "
               << fileName;
    fInputFile.reset();
    return kFALSE;
  }
  fNevents = fTree->GetEntries();
  if (startEvent >= fNevents) {
    LOG(error) << "EvtCalcGenerator: startEvent " << startEvent
               << " is out of range for " << fNevents << " entries";
    fTree.reset();
    fInputFile.reset();
    return kFALSE;
  }
  fn = startEvent;

  if (!BindBranches()) {
    fTree.reset();
    fInputFile.reset();
    return kFALSE;
  }

  LOG(info) << "EvtCalcGenerator: using convert.C Events input schema";
  return kTRUE;
}

Bool_t EvtCalcGenerator::BindBranches() {
  const std::vector<std::string> requiredBranches = {
      "LLP_px",     "LLP_py", "LLP_pz", "LLP_E", "LLP_m", "LLP_pdg",
      "LLP_weight", "vtx_x",  "vtx_y",  "vtx_z", "d_px",  "d_py",
      "d_pz",       "d_E",    "d_m",    "d_pdg"};
  for (const auto& branchName : requiredBranches) {
    if (fTree->GetBranch(branchName.c_str()) == nullptr) {
      LOG(error) << "EvtCalcGenerator: Events tree is missing required branch "
                 << branchName;
      return kFALSE;
    }
  }

  bool success = true;
  success &= fTree->SetBranchAddress("LLP_px", &fMotherPx) >= 0;
  success &= fTree->SetBranchAddress("LLP_py", &fMotherPy) >= 0;
  success &= fTree->SetBranchAddress("LLP_pz", &fMotherPz) >= 0;
  success &= fTree->SetBranchAddress("LLP_E", &fMotherE) >= 0;
  success &= fTree->SetBranchAddress("LLP_m", &fMotherMass) >= 0;
  success &= fTree->SetBranchAddress("LLP_pdg", &fMotherPdg) >= 0;
  success &= fTree->SetBranchAddress("LLP_weight", &fDecayProbability) >= 0;
  success &= fTree->SetBranchAddress("vtx_x", &fVertexX) >= 0;
  success &= fTree->SetBranchAddress("vtx_y", &fVertexY) >= 0;
  success &= fTree->SetBranchAddress("vtx_z", &fVertexZ) >= 0;
  success &= fTree->SetBranchAddress("d_px", &fDaughterPx) >= 0;
  success &= fTree->SetBranchAddress("d_py", &fDaughterPy) >= 0;
  success &= fTree->SetBranchAddress("d_pz", &fDaughterPz) >= 0;
  success &= fTree->SetBranchAddress("d_E", &fDaughterE) >= 0;
  success &= fTree->SetBranchAddress("d_m", &fDaughterMass) >= 0;
  success &= fTree->SetBranchAddress("d_pdg", &fDaughterPdg) >= 0;
  if (!success) {
    LOG(error) << "EvtCalcGenerator: failed to bind one or more branches in "
                  "the Events tree";
    return kFALSE;
  }
  return kTRUE;
}

Bool_t EvtCalcGenerator::ValidateDaughters() const {
  if (fDaughterPx == nullptr || fDaughterPy == nullptr ||
      fDaughterPz == nullptr || fDaughterE == nullptr ||
      fDaughterMass == nullptr || fDaughterPdg == nullptr) {
    LOG(error) << "EvtCalcGenerator: null daughter vector in Events tree";
    return kFALSE;
  }
  const auto size = fDaughterPx->size();
  if (fDaughterPy->size() != size || fDaughterPz->size() != size ||
      fDaughterE->size() != size || fDaughterMass->size() != size ||
      fDaughterPdg->size() != size) {
    LOG(error) << "EvtCalcGenerator: inconsistent daughter vector sizes in "
                  "Events tree entry "
               << fn;
    return kFALSE;
  }
  return kTRUE;
}
// -----   Destructor   ----------------------------------------------------
EvtCalcGenerator::~EvtCalcGenerator() = default;

// -----   Passing the event   -------------------------------------------
Bool_t EvtCalcGenerator::ReadEvent(FairPrimaryGenerator* cpg) {
  if (fn >= fNevents) {
    LOG(warning) << "End of input file. Rewind.";
    fn = 0;
  }

  if (fTree->GetEntry(fn) <= 0) {
    LOG(error) << "EvtCalcGenerator: failed to read input entry " << fn;
    return kFALSE;
  }
  if (!ValidateDaughters()) {
    return kFALSE;
  }
  fn++;
  if (fn % 100 == 0) LOGF(info, "Info EvtCalcGenerator: event nr %d", fn);

  const auto nDaughters = fDaughterPx->size();
  // Vertex coordinates in the SHiP reference frame, expressed in [cm]
  Double_t space_unit_conv = 100.;                                    // m to cm
  Double_t coord_shift = (zDecayVolume - ztarget) / space_unit_conv;  // units m
  Double_t vx_transf = fVertexX * space_unit_conv;                  // units cm
  Double_t vy_transf = fVertexY * space_unit_conv;                  // units cm
  Double_t vz_transf = (fVertexZ - coord_shift) * space_unit_conv;  // units cm

  Double_t c = 2.99792458e+10;  // speed of light [cm/s]
  Double_t tof = TMath::Sqrt(vx_transf * vx_transf + vy_transf * vy_transf +
                             vz_transf * vz_transf) /
                 c;
  Double_t decay_prob = fDecayProbability;

  // Mother LLP
  Bool_t wanttracking = false;
  cpg->AddTrack(fMotherPdg, fMotherPx, fMotherPy, fMotherPz, vx_transf,
                vy_transf, vz_transf, -1., wanttracking, fMotherE, tof,
                decay_prob);

  wanttracking = true;

  // Secondaries
  for (std::size_t iPart = 0; iPart < nDaughters; ++iPart) {
    const auto pdg_dau = fDaughterPdg->at(iPart);
    if (pdg_dau != -999) {
      cpg->AddTrack(pdg_dau, fDaughterPx->at(iPart), fDaughterPy->at(iPart),
                    fDaughterPz->at(iPart), vx_transf, vy_transf, vz_transf, 0.,
                    wanttracking, fDaughterE->at(iPart), tof, decay_prob);
    }
  }

  return kTRUE;
}
