/**
 * CourtCalendar - FullCalendar integration for court availability
 * Shows time slots with booked/available status
 */

import { useEffect, useRef } from 'react';
import FullCalendar from '@fullcalendar/react';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import type { EventClickArg, DateSelectArg } from '@fullcalendar/core';
import type { AvailabilityResponse } from '../../types/reservation';
import { mapAvailabilityToEvents } from '../../lib/mappers/reservations';

interface CourtCalendarProps {
  availability: AvailabilityResponse | null;
  selectedDate: string;
  loading?: boolean;
  onSlotClick?: (start: Date, end: Date, courtId: number) => void;
}

export default function CourtCalendar({
  availability,
  selectedDate,
  loading = false,
  onSlotClick
}: CourtCalendarProps) {
  const calendarRef = useRef<FullCalendar>(null);

  // Map availability to events
  const events = availability ? mapAvailabilityToEvents(availability) : [];

  // Handle slot click (for creating reservation)
  const handleDateSelect = (selectInfo: DateSelectArg) => {
    if (onSlotClick && availability) {
      // For now, use first court as default
      // TODO: In future, let user select court or show multiple courts as resources
      const courtId = availability.courts[0]?.id;
      if (courtId) {
        onSlotClick(selectInfo.start, selectInfo.end, courtId);
      }
    }
    // Unselect immediately
    selectInfo.view.calendar.unselect();
  };

  // Handle event click (for viewing/editing reservation)
  const handleEventClick = (clickInfo: EventClickArg) => {
    const { event } = clickInfo;
    const { reservedByMe, status } = event.extendedProps;

    if (reservedByMe) {
      alert(`Twoja rezerwacja: ${event.title}\n${event.startStr} - ${event.endStr}`);
    } else if (status === 'booked') {
      alert('Ten slot jest już zarezerwowany');
    }
  };

  return (
    <div className="relative">
      {loading && (
        <div className="absolute inset-0 bg-white/50 flex items-center justify-center z-10 rounded-lg">
          <div className="w-8 h-8 border-4 border-[var(--color-secondary)] border-t-transparent rounded-full animate-spin"></div>
        </div>
      )}

      <div className="fullcalendar-wrapper">
        <FullCalendar
          ref={calendarRef}
          plugins={[timeGridPlugin, interactionPlugin]}
          initialView="timeGridDay"
          initialDate={selectedDate}
          headerToolbar={false}
          allDaySlot={false}
          slotDuration="00:30:00"
          slotMinTime="06:00:00"
          slotMaxTime="23:00:00"
          nowIndicator={true}
          height="auto"
          expandRows={true}
          slotLabelFormat={{
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
          }}
          eventTimeFormat={{
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
          }}
          locale="pl"
          firstDay={1}
          weekends={true}
          selectable={true}
          selectMirror={true}
          select={handleDateSelect}
          eventClick={handleEventClick}
          events={events}
          eventContent={(eventInfo) => {
            const { reservedByMe, status } = eventInfo.event.extendedProps;
            return (
              <div className="fc-event-main-frame">
                <div className="fc-event-title-container">
                  <div className="fc-event-title fc-sticky">
                    {eventInfo.event.title}
                    {reservedByMe && <span className="ml-1 text-xs">✓</span>}
                  </div>
                </div>
              </div>
            );
          }}
        />
      </div>
    </div>
  );
}
