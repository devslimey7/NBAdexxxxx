#!/usr/bin/env python3
"""
Export development database data to SQL insert statements for production migration.
Run this script from the nbadex directory.
"""
import os
import sys
import asyncio
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tortoise import Tortoise

def get_database_url():
    url = os.environ.get("DATABASE_URL") or os.environ.get("BALLSDEXBOT_DB_URL")
    if url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgres://", 1)
    return url

async def export_data():
    await Tortoise.init(
        db_url=get_database_url(),
        modules={"models": ["ballsdex.core.models"]}
    )
    
    conn = Tortoise.get_connection("default")
    
    tables_to_export = [
        ("economy", "id,name,icon"),
        ("regime", "id,name,background"),
        ("special", "id,name,catch_phrase,start_date,end_date,rarity,background,emoji,tradeable,hidden,credits"),
        ("ball", "id,country,short_name,catch_names,translations,health,attack,rarity,enabled,tradeable,emoji_id,wild_card,collection_card,credits,capacity_name,capacity_description,capacity_logic,created_at,economy_id,regime_id,catch_value,catch_reward,quicksell_value"),
        ("player", "id,discord_id,donation_policy,privacy_policy,mention_policy,friend_policy,trade_cooldown_policy,extra_data,coins"),
        ("guildconfig", "id,guild_id,spawn_channel,enabled,silent"),
        ("blacklistedid", "id,discord_id,moderator_id,reason,date"),
        ("blacklistedguild", "id,guild_id,moderator_id,reason,date"),
        ("ballinstance", "id,ball_id,player_id,catch_date,server_id,spawned_time,trade_count,special_id,health_bonus,attack_bonus,shiny,favorite,tradeable,locked"),
    ]
    
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    for table_name, columns in tables_to_export:
        print(f"Exporting {table_name}...")
        try:
            result = await conn.execute_query(f"SELECT {columns} FROM {table_name} ORDER BY id")
            rows = result[1]
            
            if not rows:
                print(f"  No data in {table_name}")
                continue
                
            output_file = os.path.join(output_dir, f"{table_name}_data.sql")
            with open(output_file, 'w') as f:
                f.write(f"-- {table_name} data export\n")
                f.write(f"-- Total rows: {len(rows)}\n\n")
                
                cols = columns.split(',')
                for row in rows:
                    values = []
                    for i, col in enumerate(cols):
                        val = row[col] if isinstance(row, dict) else row[i]
                        if val is None:
                            values.append("NULL")
                        elif isinstance(val, bool):
                            values.append("TRUE" if val else "FALSE")
                        elif isinstance(val, (int, float)):
                            values.append(str(val))
                        elif isinstance(val, dict):
                            json_str = json.dumps(val).replace("'", "''")
                            values.append(f"'{json_str}'")
                        else:
                            escaped = str(val).replace("'", "''")
                            values.append(f"'{escaped}'")
                    
                    f.write(f"INSERT INTO {table_name} ({columns}) VALUES ({', '.join(values)});\n")
                
                f.write(f"\n-- Reset sequence\n")
                f.write(f"SELECT setval('{table_name}_id_seq', (SELECT MAX(id) FROM {table_name}));\n")
            
            print(f"  Exported {len(rows)} rows to {output_file}")
            
        except Exception as e:
            print(f"  Error exporting {table_name}: {e}")
    
    await Tortoise.close_connections()
    print("\nExport complete! SQL files are in the migration_scripts directory.")

if __name__ == "__main__":
    asyncio.run(export_data())
