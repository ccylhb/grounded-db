import type { APIRoute } from "astro";
import weapons from "../data/weapons.json";
import creatures from "../data/creatures.json";
import armor from "../data/armor.json";
import consumables from "../data/consumables.json";
import trinkets from "../data/trinkets.json";

interface Entry {
  t: string;
  u: string;
  k: string;
  i?: string;
}

export const GET: APIRoute = () => {
  const tools: Entry[] = [
    { t: "Creature Weakness Cheat Sheet", u: "/rankings/", k: "Tool", i: "/icons/Ladybug.png" },
    { t: "Weapon Damage Rankings", u: "/rankings/", k: "Tool" },
    { t: "Armor Sets Ranked", u: "/rankings/", k: "Tool" },
    { t: "Smoothie Planner", u: "/calculator/", k: "Tool" },
    { t: "Loot Table — where to farm every material", u: "/loot/", k: "Tool" },
  ];
  const items: Entry[] = [
    ...weapons.map((w) => ({ t: w.title, u: `/weapons/${w.slug}/`, k: w.type || "Weapon", i: w.icon || "" })),
    ...creatures.map((c) => ({ t: c.title, u: `/creatures/${c.slug}/`, k: "Creature", i: c.icon || "" })),
    ...armor.map((a) => ({ t: a.title, u: `/armor/${a.slug}/`, k: "Armor", i: a.icon || "" })),
    ...consumables.map((c) => ({ t: c.title, u: `/consumables/${c.slug}/`, k: "Consumable", i: c.icon || "" })),
    ...trinkets.map((t) => ({ t: t.title, u: `/trinkets/${t.slug}/`, k: "Trinket", i: t.icon || "" })),
  ];
  return new Response(JSON.stringify({ tools, items }), {
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
};
