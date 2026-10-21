"use client";

// Fallback 2D: sumber data dan aturan penempatan yang sama dengan 3D (lib/office/model), tanpa WebGL.
import { ROOM_ORDER, type Avatar, type RoomId } from "@/lib/office/model";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export function Office2D({ avatars, selected, onSelect }: { avatars: Avatar[]; selected: string | null; onSelect: (role: string) => void }) {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  return (
    <div className="office2d" role="group" aria-label={t("office.title")}>
      {ROOM_ORDER.map((room: RoomId) => {
        const here = avatars.filter((a) => a.room === room);
        return (
          <section key={room} className="room" data-room={room}>
            <h4>{label(`office.room.${room}`)}</h4>
            {room === "ceo" && <p className="small muted">{t("office.ceoHint")}</p>}
            {room === "lounge" && here.length > 0 && <p className="small muted">{t("office.loungeHint")}</p>}
            <ul>
              {here.map((a) => (
                <li key={a.role}>
                  <button type="button" className="agentchip" data-pose={a.pose} data-tone={a.tone} aria-pressed={selected === a.role} onClick={() => onSelect(a.role)}>
                    <strong>{label(`role.${a.role}`)}</strong>
                    <span className="badge" data-agent={a.status}>{label(`agent.${a.status}`)}</span>
                    {a.queued > 0 && <span className="small muted"> +{a.queued}</span>}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
