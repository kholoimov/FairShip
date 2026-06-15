# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

import global_variables
import ROOT
import shipunit as u
from BaseDetector import BaseDetector


class UpstreamTaggerDetector(BaseDetector):
    def __init__(self, name, intree, outtree=None) -> None:
        super().__init__(name, intree, outtree=outtree)
        self.mc_points = ROOT.std.vector("UpstreamTaggerPoint")()
        self.mc_branch = self.outtree.Branch("UpstreamTaggerPoint", self.mc_points, 32000, 99)

    def delete(self) -> None:
        super().delete()
        self.mc_points.clear()

    @staticmethod
    def _snap_to_tile_center(value: float, offset: float, pitch: float) -> float:
        return ((value + offset) // pitch) * pitch + pitch / 2.0 - offset

    def digitize(self) -> None:
        ship_geo = global_variables.ShipGeo
        box_x = ship_geo.UpstreamTagger.BoxX
        box_y = ship_geo.UpstreamTagger.BoxY
        z_center = ship_geo.UpstreamTagger.Z_Position
        fine_pitch = 5.0 * u.cm
        coarse_pitch = 10.0 * u.cm
        central_half_size = 50.0 * u.cm
        time_res = ship_geo.UpstreamTagger.TimeResolution

        for aMCPoint in self.intree.UpstreamTaggerPoint:
            self.mc_points.push_back(aMCPoint)
            x = aMCPoint.GetX()
            y = aMCPoint.GetY()
            if abs(x) < central_half_size and abs(y) < central_half_size:
                center_x = self._snap_to_tile_center(x, central_half_size, fine_pitch)
                center_y = self._snap_to_tile_center(y, central_half_size, fine_pitch)
            else:
                center_x = self._snap_to_tile_center(x, box_x / 2.0, coarse_pitch)
                center_y = self._snap_to_tile_center(y, box_y / 2.0, coarse_pitch)
            time = ROOT.gRandom.Gaus(aMCPoint.GetTime() + self.intree.t0, time_res)
            aHit = ROOT.UpstreamTaggerHit(
                aMCPoint.GetDetectorID(), center_x, center_y, z_center, time
            )
            self.det.push_back(aHit)
