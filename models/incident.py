            # If road-based approach didn't create enough divisions, subdivide existing ones
            if len(divisions) < num_divisions and len(divisions) > 0:
                print(f"Road-based approach created {len(divisions)} divisions, need {num_divisions}. Subdividing...")
                divisions = self._subdivide_divisions(divisions, num_divisions, polygon)

            # Only fall back to grid if we have no valid divisions at all
            if len(divisions) == 0:
                print("Road-based approach created no valid divisions, falling back to grid")
                return []

            print(f"Successfully created {len(divisions)} road-aware divisions")
            return divisions