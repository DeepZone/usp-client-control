import json
import os
import tempfile
import unittest

os.environ.setdefault("APP_SECRET", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "TestPassword123!")
os.environ.setdefault("MQTT_CONTROLLER_PASSWORD", "test")

import app


class LiveProfileTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        app.DB_PATH = os.path.join(self.tempdir.name, "controller.db")
        app.initialize_database()
        timestamp = app.now()
        with app.db() as connection:
            connection.execute("INSERT INTO agents(endpoint_id,first_seen,last_seen) VALUES(?,?,?)", ("agent", timestamp, timestamp))
            connection.executemany(
                "INSERT INTO parameters(endpoint_id,path,value,updated_at) VALUES(?,?,?,?)",
                [
                    ("agent", "Device.DeviceInfo.ProcessStatus.CPUUsage", "12", timestamp),
                    ("agent", "Device.WiFi.Radio.1.ChannelUtilization", "25", timestamp),
                    ("agent", "Device.WiFi.AccessPoint.1.AssociatedDevice.1.SignalStrength", "-52", timestamp),
                ],
            )
            rows = [
                ("Device.DeviceInfo.ProcessStatus.CPUUsage", "parameter", "CPUUsage", "PARAM_READ_ONLY", "PARAM_UNSIGNED_INT", "VALUE_CHANGE_ALLOWED", {}),
                ("Device.WiFi.Radio.{i}.ChannelUtilization", "parameter", "ChannelUtilization", "PARAM_READ_ONLY", "PARAM_UNSIGNED_INT", "VALUE_CHANGE_WILL_IGNORE", {}),
                ("Device.WiFi.AccessPoint.{i}.AssociatedDevice.{i}.SignalStrength", "parameter", "SignalStrength", "PARAM_READ_ONLY", "PARAM_INT", "VALUE_CHANGE_ALLOWED", {}),
                ("Device.WiFi.AccessPoint.{i}.AssociatedDevice.{i}.", "object", "", "OBJ_READ_ONLY", "", "", {"multi_instance": True}),
                ("Device.DeviceInfo.Boot!", "event", "Boot!", "", "", "", {"args": []}),
            ]
            connection.executemany(
                "INSERT INTO model_schema(endpoint_id,path,kind,name,access,value_type,value_change,metadata,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                [("agent", *row[:6], json.dumps(row[6]), timestamp) for row in rows],
            )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_profile_resolves_instances_and_separates_polling(self):
        profile = app.automatic_live_profile("agent")
        self.assertIn("Device.DeviceInfo.", profile["ValueChange"])
        self.assertIn("Device.WiFi.AccessPoint.", profile["ValueChange"])
        self.assertEqual(profile["capability_counts"]["ValueChange"], 2)
        self.assertIn("Device.WiFi.Radio.1.ChannelUtilization", profile["poll_paths"])
        self.assertNotIn("Device.DeviceInfo.ProcessStatus.CPUUsage", profile["poll_paths"])
        self.assertIn("Device.WiFi.AccessPoint.*.AssociatedDevice.", profile["ObjectCreation"])
        self.assertIn("Device.WiFi.AccessPoint.*.AssociatedDevice.*.", profile["ObjectDeletion"])
        self.assertIn("Device.DeviceInfo.", profile["Event"])

    def test_reference_lists_stay_below_agent_limit(self):
        paths = [f"Device.WiFi.Radio.{index}.ChannelUtilization" for index in range(1, 30)]
        groups = app.pack_subscription_references(paths)
        self.assertEqual(paths, [path for group in groups for path in group.split(",")])
        self.assertTrue(all(len(group) <= 240 for group in groups))


if __name__ == "__main__":
    unittest.main()
