# SPDX-License-Identifier: GPL-2.0-or-later
import struct

from protocol.constants import CMD_VIA_VIAL_PREFIX, CMD_VIAL_DYNAMIC_ENTRY_OP


class BaseProtocol:
    vial_protocol = None
    usb_send = NotImplemented
    dev = None

    macro_count = 0
    macro_memory = 0
    macro = b""

    def _retrieve_dynamic_entries(self, cmd, count, fmt):
        import time
        import logging

        out = []
        sz = struct.calcsize(fmt)
        for x in range(count):
            entry_data = None
            for attempt in range(3):
                try:
                    data = self.usb_send(
                        self.dev,
                        struct.pack("BBBB", CMD_VIA_VIAL_PREFIX, CMD_VIAL_DYNAMIC_ENTRY_OP, cmd, x),
                        retries=3
                    )
                    if data and data[0] == 0:
                        entry_data = struct.unpack(fmt, data[1:1 + sz])
                        break
                except Exception:
                    pass
                time.sleep(0.05)

            if entry_data is None:
                logging.warning("failed retrieving dynamic={} entry {} from the device, defaulting".format(cmd, x))
                entry_data = struct.unpack(fmt, b"\x00" * sz)
            out.append(entry_data)
        return out
