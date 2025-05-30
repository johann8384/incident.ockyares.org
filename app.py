    def submit_unit_status_update(self, update_data):
        """Submit unit status update and update division progress"""
        conn = self.connect_db()
        cursor = conn.cursor()

        try:
            # Insert status update record
            cursor.execute("""
                INSERT INTO unit_status_updates (
                    incident_id, unit_id, officer_name, status_change,
                    progress_percentage, need_assistance, comment,
                    location_point, location_source, update_timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s)
                RETURNING id
            """, (
                update_data['incident_id'],
                update_data['unit_id'],
                update_data['officer_name'],
                update_data['status_change'],
                update_data.get('progress_percentage'),
                update_data.get('need_assistance', False),
                update_data.get('comment'),
                float(update_data['longitude']) if update_data.get('longitude') else None,
                float(update_data['latitude']) if update_data.get('latitude') else None,
                update_data.get('location_source', 'manual'),
                datetime.now()
            ))

            update_id = cursor.fetchone()[0]

            # Update unit status
            cursor.execute("""
                UPDATE units 
                SET unit_status = %s, updated_at = NOW()
                WHERE incident_id = %s AND unit_id = %s
            """, (
                update_data['status_change'],
                update_data['incident_id'],
                update_data['unit_id']
            ))

            # Update division progress if unit has an assignment and progress is provided
            if update_data.get('progress_percentage') is not None:
                # Get unit's assigned division
                cursor.execute("""
                    SELECT assigned_division FROM units
                    WHERE incident_id = %s AND unit_id = %s AND assigned_division IS NOT NULL
                """, (update_data['incident_id'], update_data['unit_id']))
                
                result = cursor.fetchone()
                if result:
                    division_id = result[0]
                    
                    # Update the division's progress
                    cursor.execute("""
                        UPDATE search_divisions 
                        SET progress_percentage = %s, updated_at = NOW()
                        WHERE incident_id = %s AND division_id = %s
                    """, (
                        update_data['progress_percentage'],
                        update_data['incident_id'],
                        division_id
                    ))
                    
                    app.logger.info(f"Updated division {division_id} progress to {update_data['progress_percentage']}%")

            conn.commit()
            app.logger.info(f"Unit {update_data['unit_id']} status updated to {update_data['status_change']}")
            return update_id

        except Exception as e:
            conn.rollback()
            app.logger.error(f"Failed to submit unit status update: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()

    def get_unit_status_updates(self, incident_id, unit_id=None):
        """Get status updates for incident or specific unit"""
        conn = self.connect_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        try:
            if unit_id:
                cursor.execute("""
                    SELECT id, unit_id, officer_name, status_change, progress_percentage,
                           need_assistance, comment, location_source, update_timestamp,
                           ST_X(location_point) as longitude, ST_Y(location_point) as latitude
                    FROM unit_status_updates 
                    WHERE incident_id = %s AND unit_id = %s
                    ORDER BY update_timestamp DESC
                """, (incident_id, unit_id))
            else:
                cursor.execute("""
                    SELECT id, unit_id, officer_name, status_change, progress_percentage,
                           need_assistance, comment, location_source, update_timestamp,
                           ST_X(location_point) as longitude, ST_Y(location_point) as latitude
                    FROM unit_status_updates 
                    WHERE incident_id = %s
                    ORDER BY update_timestamp DESC
                """, (incident_id,))

            updates = []
            for update in cursor.fetchall():
                update_dict = dict(update)
                if update_dict['update_timestamp']:
                    update_dict['update_timestamp'] = update_dict['update_timestamp'].isoformat()
                updates.append(update_dict)

            app.logger.info(f"Retrieved {len(updates)} status updates for incident {incident_id}")
            return updates

        except Exception as e:
            app.logger.error(f"Failed to get status updates: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()