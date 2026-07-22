// SPDX-License-Identifier: LGPL-3.0-or-later
// SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP
// Collaboration

#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

#include "EvtCalcGenerator.h"
#include "FairPrimaryGenerator.h"
#include "TFile.h"
#include "TTree.h"

namespace {
class TestableEvtCalcGenerator : public EvtCalcGenerator {
 public:
  bool LoadFirstEntry() { return fTree && fTree->GetEntry(0) > 0; }
  double MotherPx() const { return fMotherPx; }
  double MotherPdg() const { return fMotherPdg; }
  double DaughterPdg() const { return fDaughterPdg->at(0); }
  double DaughterCount() const { return fDaughterPx->size(); }
};

class CapturingPrimaryGenerator : public FairPrimaryGenerator {
 public:
  struct Track {
    Int_t pdg;
    Double_t px;
    Int_t parent;
  };

  void AddTrack(Int_t pdg, Double_t px, Double_t, Double_t, Double_t, Double_t,
                Double_t, Int_t parent, Bool_t, Double_t, Double_t, Double_t,
                TMCProcess) override {
    tracks.push_back({pdg, px, parent});
  }

  std::vector<Track> tracks;
};

std::filesystem::path CreateConvertSchemaFile() {
  const auto path =
      std::filesystem::temp_directory_path() / "evtcalc_convert_schema.root";
  TFile output(path.c_str(), "RECREATE");
  TTree tree("Events", "LLP Simulation Data");

  Float_t motherPx = 1.0;
  Float_t motherPy = 2.0;
  Float_t motherPz = 3.0;
  Float_t motherEnergy = 4.5;
  Float_t motherMass = 1.5;
  Int_t motherPdg = 9900015;
  Float_t weight = 0.25;
  Float_t vertexX = 0.01;
  Float_t vertexY = -0.02;
  Float_t vertexZ = 12.0;
  std::vector<float> daughterPx = {0.1F, -0.1F};
  std::vector<float> daughterPy = {0.2F, -0.2F};
  std::vector<float> daughterPz = {0.3F, 0.4F};
  std::vector<float> daughterEnergy = {0.5F, 0.6F};
  std::vector<float> daughterMass = {0.0F, 0.0F};
  std::vector<int> daughterPdg = {11, -11};

  tree.Branch("LLP_px", &motherPx, "LLP_px/F");
  tree.Branch("LLP_py", &motherPy, "LLP_py/F");
  tree.Branch("LLP_pz", &motherPz, "LLP_pz/F");
  tree.Branch("LLP_E", &motherEnergy, "LLP_E/F");
  tree.Branch("LLP_m", &motherMass, "LLP_m/F");
  tree.Branch("LLP_pdg", &motherPdg, "LLP_pdg/I");
  tree.Branch("LLP_weight", &weight, "LLP_weight/F");
  tree.Branch("vtx_x", &vertexX, "vtx_x/F");
  tree.Branch("vtx_y", &vertexY, "vtx_y/F");
  tree.Branch("vtx_z", &vertexZ, "vtx_z/F");
  tree.Branch("d_px", &daughterPx);
  tree.Branch("d_py", &daughterPy);
  tree.Branch("d_pz", &daughterPz);
  tree.Branch("d_E", &daughterEnergy);
  tree.Branch("d_m", &daughterMass);
  tree.Branch("d_pdg", &daughterPdg);
  tree.Fill();
  tree.Write();
  output.Close();
  return path;
}

}  // namespace

int main(int argc, char** argv) {
  const bool useExternalInput = argc > 1;
  const auto inputPath = useExternalInput ? std::filesystem::path(argv[1])
                                          : CreateConvertSchemaFile();
  TestableEvtCalcGenerator generator;
  if (!generator.Init(inputPath.c_str()) || generator.GetNevents() <= 0) {
    std::cerr << "Failed to initialize convert.C Events schema" << std::endl;
    return 1;
  }
  if (!generator.LoadFirstEntry()) {
    std::cerr << "Failed to read first convert.C Events entry" << std::endl;
    return 1;
  }
  if (!useExternalInput &&
      (generator.MotherPx() != 1.F || generator.MotherPdg() != 9900015. ||
       generator.DaughterCount() != 2. || generator.DaughterPdg() != 11.)) {
    std::cerr << "Incorrect values read from convert.C Events schema"
              << std::endl;
    return 1;
  }

  CapturingPrimaryGenerator primaryGenerator;
  generator.SetPositions(0., 0.);
  if (!generator.ReadEvent(&primaryGenerator) ||
      primaryGenerator.tracks.empty()) {
    std::cerr << "Failed to generate tracks from convert.C Events schema"
              << std::endl;
    return 1;
  }
  if (!useExternalInput && (primaryGenerator.tracks.size() != 3 ||
                            primaryGenerator.tracks[0].pdg != 9900015 ||
                            primaryGenerator.tracks[0].px != 1.F ||
                            primaryGenerator.tracks[0].parent != -1 ||
                            primaryGenerator.tracks[1].pdg != 11 ||
                            primaryGenerator.tracks[1].parent != 0)) {
    std::cerr << "Incorrect tracks generated from convert.C Events schema"
              << std::endl;
    return 1;
  }
  if (!useExternalInput) std::filesystem::remove(inputPath);

  std::cout << "EvtCalcGenerator convert.C schema test passed" << std::endl;
  return 0;
}
